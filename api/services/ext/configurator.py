import asyncio
import contextlib
import json
import re
import time
from collections.abc import Awaitable
from typing import Any, cast

from dishka import AsyncContainer, Scope
from fastapi import HTTPException, Request
from fastapi.security import SecurityScopes
from paramiko.channel import Channel
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import CommaSeparatedStrings

from api import constants, models, utils
from api.ext.ssh import ServerEnv, create_ssh_client
from api.logging import get_logger, log_errors
from api.redis import Redis
from api.schemas.configurator import (
    ConfiguratorAdvancedSettings,
    ConfiguratorCoinDescription,
    ConfiguratorDeploySettings,
    ConfiguratorDomainSettings,
    ConfiguratorServerSettings,
)
from api.schemas.misc import SSHSettings
from api.schemas.policies import Policy
from api.schemas.tasks import DeployTaskMessage
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.types import AuthServiceProtocol, TasksBroker
from api.utils.common import str_to_bool

COLOR_PATTERN = re.compile(r"\x1b[^m]*m")
BASH_INTERMEDIATE_COMMAND = 'echo "end-of-command $(expr 1 + 1)"'
INTERMEDIATE_OUTPUT = "end-of-command 2"
MAX_OUTPUT_WAIT = 10
OUTPUT_INTERVAL = 0.5
BUFFER_SIZE = 17640

REDIS_KEY = "bitcart_configurator_ext"
KEY_TTL = 60 * 60 * 24  # 1 day

logger = get_logger(__name__)


class ConfiguratorService:
    def __init__(
        self,
        settings: Settings,
        redis_pool: Redis,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
        container: AsyncContainer,
    ) -> None:
        self.settings = settings
        self.redis_pool = redis_pool
        self.broker = broker
        self.plugin_registry = plugin_registry
        self.container = container

    @staticmethod
    def collect_server_settings(ssh_settings: SSHSettings) -> ConfiguratorServerSettings:  # pragma: no cover
        settings = ConfiguratorServerSettings()
        with contextlib.suppress(Exception):
            client = create_ssh_client(ssh_settings)
            env = ServerEnv(client)
            cryptos = CommaSeparatedStrings(env.get("BITCART_CRYPTOS", "btc"))
            for crypto in cryptos:
                symbol = crypto.upper()
                network = env.get(f"{symbol}_NETWORK", "mainnet")
                lightning = str_to_bool(env.get(f"{symbol}_LIGHTNING", "false"))
                settings.coins[crypto] = ConfiguratorCoinDescription(network=network, lightning=lightning)
            domain = env.get("BITCART_HOST", "")
            reverse_proxy = env.get("BITCART_REVERSEPROXY", "nginx-https")
            is_https = reverse_proxy in constants.HTTPS_REVERSE_PROXIES
            settings.domain_settings = ConfiguratorDomainSettings(domain=domain, https=is_https)
            installation_pack = env.get("BITCART_INSTALL", "all")
            additional_components = list(CommaSeparatedStrings(env.get("BITCART_ADDITIONAL_COMPONENTS", "")))
            settings.advanced_settings = ConfiguratorAdvancedSettings(
                installation_pack=installation_pack, additional_components=additional_components
            )
            client.close()
        return settings

    async def get_server_settings(
        self, ssh_settings: SSHSettings | None = None, user: models.User | None = None
    ) -> ConfiguratorServerSettings:
        if not ssh_settings:
            if not user:
                raise HTTPException(401, "Unauthorized")
            ssh_settings = self.settings.ssh_settings
        server_settings = self.collect_server_settings(ssh_settings)
        await self.plugin_registry.run_hook("configurator_server_settings", server_settings)
        return server_settings

    async def get_deploy_result(self, request: Request, deploy_id: str) -> dict[str, Any]:
        await self.authenticate_request(request)
        data = await self.get_task(deploy_id)
        if not data:
            raise HTTPException(404, f"Deployment result {deploy_id} does not exist!")
        return data

    async def generate_deployment(self, request: Request, deploy_settings: ConfiguratorDeploySettings) -> dict[str, Any]:
        this_machine = deploy_settings.mode == "Current"
        scopes = [constants.AuthScopes.SERVER_MANAGEMENT] if this_machine else []
        await self.authenticate_request(request, scopes=scopes)
        script = self.create_bash_script(deploy_settings)
        ssh_settings = self.settings.ssh_settings if this_machine else SSHSettings(**deploy_settings.ssh_settings.model_dump())
        return await self.create_new_task(script, ssh_settings, deploy_settings.mode == "Manual")

    @staticmethod
    def install_package(package: str) -> str:
        return f"apt-get update && apt-get install -y {package}"

    @classmethod
    def create_bash_script(cls, settings: ConfiguratorDeploySettings) -> str:
        git_repo = settings.advanced_settings.bitcart_docker_repository or constants.DOCKER_REPO_URL
        root_password = settings.ssh_settings.root_password
        reverseproxy = "nginx-https" if settings.domain_settings.https else "nginx"
        cryptos_str = ",".join(settings.coins.keys())
        installation_pack = settings.advanced_settings.installation_pack
        additional_components = sorted(set(settings.additional_services + settings.advanced_settings.additional_components))
        domain = settings.domain_settings.domain or "bitcart.local"
        script = ""
        if not root_password:
            script += "sudo su -"
        else:
            script += f'echo "{root_password}" | sudo -S sleep 1 && sudo su -'
        script += "\n"
        script += f"{cls.install_package('git')}\n"
        script += (
            'if [ -d "bitcart-docker" ]; then echo "existing bitcart-docker folder found, pulling instead of cloning.";'
            " git pull; fi\n"
        )
        script += (
            f'if [ ! -d "bitcart-docker" ]; then echo "cloning bitcart-docker"; git clone {git_repo} bitcart-docker; fi\n'
        )
        if git_repo != constants.DOCKER_REPO_URL:
            script += 'export BITCARTGEN_DOCKER_IMAGE="bitcart/docker-compose-generator:local"\n'
        script += f"export BITCART_HOST={domain}\n"
        if reverseproxy != "nginx-https":
            script += f"export BITCART_REVERSEPROXY={reverseproxy}\n"
        script += f"export BITCART_CRYPTOS={cryptos_str}\n"
        for symbol, coin in settings.coins.items():
            if coin.network != "mainnet":
                script += f"export {symbol.upper()}_NETWORK={coin.network}\n"
            if coin.lightning:
                script += f"export {symbol.upper()}_LIGHTNING={coin.lightning}\n"
        if installation_pack != "all":
            script += f"export BITCART_INSTALL={installation_pack}\n"
        if additional_components:
            script += f"export BITCART_ADDITIONAL_COMPONENTS={','.join(additional_components)}\n"
        script += "cd bitcart-docker\n"
        script += "./setup.sh\n"
        return script

    @staticmethod
    def remove_intermediate_lines(output: str) -> str:
        newoutput = ""
        for line in output.splitlines():
            if BASH_INTERMEDIATE_COMMAND in line or INTERMEDIATE_OUTPUT in line:
                continue
            newoutput += line + "\n"
        return newoutput

    @staticmethod
    def remove_colors(output: str) -> str:
        return "\n".join([COLOR_PATTERN.sub("", line) for line in output.split("\n")])

    @staticmethod
    def send_command(channel: Channel, command: str) -> str:
        channel.sendall(command + "\n")  # type: ignore
        channel.sendall(f"{BASH_INTERMEDIATE_COMMAND}\n")  # type: ignore # To find command end
        finished = False
        counter = 0
        output = ""
        while not finished:
            if counter > MAX_OUTPUT_WAIT:
                counter = 0
                channel.sendall(f"{BASH_INTERMEDIATE_COMMAND}\n")  # type: ignore
            while channel.recv_ready():
                data = channel.recv(BUFFER_SIZE).decode()
                output += data
                if INTERMEDIATE_OUTPUT in data:
                    finished = True
            time.sleep(OUTPUT_INTERVAL)
            counter += 1
        return output

    @classmethod
    def execute_ssh_commands(cls, commands: str, ssh_settings: SSHSettings) -> tuple[bool, str]:
        try:
            client = create_ssh_client(ssh_settings)
            channel = client.invoke_shell()
            output = ""
            for command in commands.splitlines():
                output += cls.send_command(channel, command)
            output = cls.remove_intermediate_lines(output)
            output = cls.remove_colors(output)
            channel.close()
            client.close()
            return True, output
        except Exception as e:
            return False, str(e)

    async def set_task(self, task_id: str, data: dict[str, Any]) -> None:
        await cast(Awaitable[int], self.redis_pool.hset(REDIS_KEY, mapping={task_id: json.dumps(data)}))

    async def create_new_task(self, script: str, ssh_settings: SSHSettings, is_manual: bool) -> dict[str, Any]:
        deploy_id = utils.common.unique_id()
        data = {
            "id": deploy_id,
            "script": script,
            "ssh_settings": ssh_settings.model_dump(),
            "success": is_manual,
            "finished": is_manual,
            "created": utils.time.now().timestamp(),
            "output": script if is_manual else "",
        }
        await self.set_task(deploy_id, data)
        if not is_manual:
            await self.broker.publish(DeployTaskMessage(task_id=deploy_id), "deploy_task")
        return data

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        data = await cast(Awaitable[str | None], self.redis_pool.hget(REDIS_KEY, task_id))
        return json.loads(data) if data else None

    async def run_deploy_task(self, task_id: str) -> None:
        task = await self.get_task(task_id)
        if not task:
            return
        logger.debug("Started deployment", task_id=task_id)
        await self.plugin_registry.run_hook("pre_deploy", task_id, task)
        import asyncio

        await asyncio.sleep(10)
        success, output = await run_in_threadpool(
            self.execute_ssh_commands, task["script"], SSHSettings(**task["ssh_settings"])
        )
        await self.plugin_registry.run_hook("post_deploy", task_id, task, success, output)
        logger.debug("Deployment finished", task_id=task_id, success=success)
        task["finished"] = True
        task["success"] = success
        task["output"] = output
        await self.set_task(task_id, task)

    async def authenticate_request(self, request: Request, scopes: list[constants.AuthScopes] | None = None) -> None:
        if scopes is None:
            scopes = []
        async with self.container(scope=Scope.REQUEST) as container:
            auth_service = await container.get(AuthServiceProtocol)
            setting_service = await container.get(SettingService)
            try:
                auth_token = await utils.authorization.auth_dependency.parse_token(request)
                await auth_service.find_user_and_check_permissions(auth_token, SecurityScopes(cast(list[str], scopes)))
            except HTTPException:
                if scopes:
                    raise
                allow_anonymous_configurator = (await setting_service.get_setting(Policy)).allow_anonymous_configurator
                if not allow_anonymous_configurator:
                    raise HTTPException(422, "Anonymous configurator access disallowed") from None

    async def refresh_pending_deployments(self) -> None:
        with log_errors(logger):
            now = utils.time.now().timestamp()
            to_delete = []
            async for key, value in self.redis_pool.hscan_iter(REDIS_KEY):
                with log_errors(logger):
                    value = json.loads(value) if value else value
                    # Remove stale deployments
                    if "created" not in value or now - value["created"] >= KEY_TTL:
                        to_delete.append(key)
                    try:
                        ssh_settings = SSHSettings(**value["ssh_settings"])
                    except ValidationError:
                        continue
                    # Mark all current instance deployments as complete as we can't do it from the worker task
                    if ssh_settings == self.settings.ssh_settings:
                        value["finished"] = True
                        value["success"] = True
                        value["output"] = "No output available. Current instance has been restarted"
                        await self.set_task(key, value)
            if to_delete:
                await cast(Awaitable[int], self.redis_pool.hdel(REDIS_KEY, *to_delete))

    async def start(self) -> None:
        asyncio.create_task(self.refresh_pending_deployments())
