import asyncio
import contextlib
import ipaddress
import json
import re
import socket
import time
from typing import Any, cast

from dishka import AsyncContainer, Scope
from fastapi import HTTPException, Request
from fastapi.security import SecurityScopes
from paramiko.channel import Channel
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import CommaSeparatedStrings

from api import constants, models, utils
from api.ext.agent import AgentError
from api.ext.ssh import ServerEnv, create_ssh_client
from api.logging import get_logger, log_errors
from api.redis import Redis
from api.schemas.configurator import (
    ConfiguratorAdvancedSettings,
    ConfiguratorCoinDescription,
    ConfiguratorDeploySettings,
    ConfiguratorDomainSettings,
    ConfiguratorServerSettings,
    ConfiguratorSSHSettings,
)
from api.schemas.misc import HostAgentJob
from api.schemas.policies import Policy
from api.schemas.tasks import DeployTaskMessage
from api.services.host_agent import HostAgentService, error_response
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
DNS_TIMEOUT = 5

logger = get_logger(__name__)


class ConfiguratorService:
    def __init__(
        self,
        settings: Settings,
        redis_pool: Redis,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
        host_agent: HostAgentService,
        container: AsyncContainer,
    ) -> None:
        self.settings = settings
        self.redis_pool = redis_pool
        self.broker = broker
        self.plugin_registry = plugin_registry
        self.host_agent = host_agent
        self.container = container
        self.plugin_registry.register_hook("host_agent_job_finished", self.job_finished)

    @staticmethod
    def build_server_settings(env: dict[str, str]) -> ConfiguratorServerSettings:
        env = {key: value for key, value in env.items() if value}
        settings = ConfiguratorServerSettings()
        for crypto in CommaSeparatedStrings(env.get("BITCART_CRYPTOS", "btc")):
            symbol = crypto.upper()
            network = env.get(f"{symbol}_NETWORK", "mainnet")
            lightning = str_to_bool(env.get(f"{symbol}_LIGHTNING", "false"))
            settings.coins[crypto] = ConfiguratorCoinDescription(network=network, lightning=lightning)
        is_https = env.get("BITCART_REVERSEPROXY", "nginx-https") in constants.HTTPS_REVERSE_PROXIES
        settings.domain_settings = ConfiguratorDomainSettings(domain=env.get("BITCART_HOST", ""), https=is_https)
        settings.advanced_settings = ConfiguratorAdvancedSettings(
            installation_pack=env.get("BITCART_INSTALL", "all"),
            additional_components=list(CommaSeparatedStrings(env.get("BITCART_ADDITIONAL_COMPONENTS", ""))),
        )
        return settings

    @classmethod
    def collect_remote_server_settings(
        cls, ssh_settings: ConfiguratorSSHSettings
    ) -> ConfiguratorServerSettings:  # pragma: no cover
        with contextlib.suppress(Exception):
            client = create_ssh_client(ssh_settings)
            try:
                return cls.build_server_settings(ServerEnv(client).env)
            finally:
                client.close()
        return ConfiguratorServerSettings()

    async def collect_current_server_settings(self) -> ConfiguratorServerSettings:
        await self.host_agent.require("get_config")
        config = await self.host_agent.call("get_config")
        return self.build_server_settings(config["settings"])

    async def get_server_settings(
        self, ssh_settings: ConfiguratorSSHSettings | None = None, user: models.User | None = None
    ) -> ConfiguratorServerSettings:
        if ssh_settings:
            server_settings = await run_in_threadpool(self.collect_remote_server_settings, ssh_settings)
        elif user:
            server_settings = await self.collect_current_server_settings()
        else:
            raise HTTPException(401, "Unauthorized")
        await self.plugin_registry.run_hook("configurator_server_settings", server_settings)
        return server_settings

    async def check_dns_entry(self, request: Request, name: str) -> bool:
        await self.authenticate_request(request)
        try:
            async with asyncio.timeout(DNS_TIMEOUT):
                addresses = await run_in_threadpool(socket.getaddrinfo, name, None)
        except Exception:
            return False
        return any(ipaddress.ip_address(sockaddr[0]).is_global for *_, sockaddr in addresses)

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
        if this_machine:
            return await self.create_current_task(deploy_settings)
        script = self.create_bash_script(deploy_settings)
        return await self.create_new_task(script, deploy_settings.ssh_settings, deploy_settings.mode == "Manual")

    @classmethod
    def create_bash_script(cls, settings: ConfiguratorDeploySettings) -> str:
        git_repo = settings.advanced_settings.bitcart_docker_repository or constants.DOCKER_REPO_URL
        root_password = settings.ssh_settings.root_password
        script = ""
        if not root_password:
            script += "sudo su -"
        else:
            script += f'echo "{root_password}" | sudo -S sleep 1 && sudo su -'
        script += "\n"
        script += "apt-get update && apt-get install -y git\n"
        script += (
            'if [ -d "bitcart-docker" ]; then echo "existing bitcart-docker folder found, pulling instead of cloning.";'
            " git pull; fi\n"
        )
        script += (
            f'if [ ! -d "bitcart-docker" ]; then echo "cloning bitcart-docker"; git clone {git_repo} bitcart-docker; fi\n'
        )
        if git_repo != constants.DOCKER_REPO_URL:
            script += 'export BITCARTGEN_DOCKER_IMAGE="bitcart/docker-compose-generator:local"\n'
        for key, value in cls.create_host_settings(settings).items():
            script += f"export {key}={value}\n"
        script += "cd bitcart-docker\n"
        script += "./setup.sh\n"
        return script

    @staticmethod
    def create_host_settings(settings: ConfiguratorDeploySettings) -> dict[str, str]:
        host_settings = {
            "BITCART_HOST": settings.domain_settings.domain or "bitcart.local",
            "BITCART_REVERSEPROXY": "nginx-https" if settings.domain_settings.https else "nginx",
            "BITCART_CRYPTOS": ",".join(settings.coins.keys()),
            "BITCART_INSTALL": settings.advanced_settings.installation_pack or "all",
            "BITCART_ADDITIONAL_COMPONENTS": ",".join(
                sorted(set(settings.additional_services + settings.advanced_settings.additional_components))
            ),
        }
        for symbol, coin in settings.coins.items():
            host_settings[f"{symbol.upper()}_NETWORK"] = coin.network or "mainnet"
            host_settings[f"{symbol.upper()}_LIGHTNING"] = "true" if coin.lightning else "false"
        return host_settings

    @staticmethod
    def remove_intermediate_lines(output: str) -> str:
        return "".join(
            f"{line}\n"
            for line in output.splitlines()
            if BASH_INTERMEDIATE_COMMAND not in line and INTERMEDIATE_OUTPUT not in line
        )

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
    def execute_ssh_commands(cls, commands: str, ssh_settings: ConfiguratorSSHSettings) -> tuple[bool, str]:
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
        await self.redis_pool.hset(REDIS_KEY, mapping={task_id: json.dumps(data)})

    async def create_new_task(self, script: str, ssh_settings: ConfiguratorSSHSettings, is_manual: bool) -> dict[str, Any]:
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
            await self.broker.publish("deploy_task", DeployTaskMessage(task_id=deploy_id))
        return data

    async def create_current_task(self, deploy_settings: ConfiguratorDeploySettings) -> dict[str, Any]:
        deploy_id = utils.common.unique_id()
        data: dict[str, Any] = {
            "id": deploy_id,
            "script": "",
            "success": False,
            "finished": False,
            "created": utils.time.now().timestamp(),
            "output": "",
        }
        try:
            await self.host_agent.require("reconfigure")
        except AgentError as e:
            data.update(finished=True, output=error_response(e)["message"])
            await self.set_task(deploy_id, data)
            return data
        await self.plugin_registry.run_hook("pre_deploy", deploy_id, data)
        try:
            data["job_id"] = (await self.host_agent.call("reconfigure", self.create_host_settings(deploy_settings)))["job_id"]
        except AgentError as e:
            data.update(finished=True, output=error_response(e)["message"])
            await self.plugin_registry.run_hook("post_deploy", deploy_id, data, False, data["output"])
        await self.set_task(deploy_id, data)
        return data

    async def job_finished(self, job: HostAgentJob) -> None:
        if job.command != "reconfigure" or (data := await self.get_task_by_job(job.job_id)) is None:
            return
        try:
            output = (await self.host_agent.job_status(job.job_id, "all"))["log"]
        except AgentError as e:
            output = e.message
        data.update(finished=True, success=job.state == "done", output=output)
        await self.set_task(data["id"], data)
        await self.plugin_registry.run_hook("post_deploy", data["id"], data, data["success"], output)

    async def get_task_by_job(self, job_id: str) -> dict[str, Any] | None:
        async for _, value in self.redis_pool.hscan_iter(REDIS_KEY):
            data = json.loads(value)
            if data.get("job_id") == job_id:
                return data
        return None

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        data = await self.redis_pool.hget(REDIS_KEY, task_id)
        return json.loads(data) if data else None

    async def run_deploy_task(self, task_id: str) -> None:
        task = await self.get_task(task_id)
        if not task:
            return
        logger.debug("Started deployment", task_id=task_id)
        await self.plugin_registry.run_hook("pre_deploy", task_id, task)
        await asyncio.sleep(10)
        success, output = await run_in_threadpool(
            self.execute_ssh_commands, task["script"], ConfiguratorSSHSettings(**task["ssh_settings"])
        )
        await self.plugin_registry.run_hook("post_deploy", task_id, task, success, output)
        logger.debug("Deployment finished", task_id=task_id, success=success)
        task["finished"] = True
        task["success"] = success
        task["output"] = output
        await self.set_task(task_id, task)

    async def authenticate_request(self, request: Request, scopes: list[constants.AuthScopes] | None = None) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            auth_service = await container.get(AuthServiceProtocol)
            setting_service = await container.get(SettingService)
            try:
                auth_token = await utils.authorization.auth_dependency.parse_token(request)
                await auth_service.find_user_and_check_permissions(auth_token, SecurityScopes(cast(list[str], scopes or [])))
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
            if to_delete:
                await self.redis_pool.hdel(REDIS_KEY, *to_delete)

    async def start(self) -> None:
        asyncio.create_task(self.refresh_pending_deployments())
