import asyncio
import contextlib
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any, cast

import aiofiles
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException

from api import utils
from api.ext.ssh import create_ssh_client, execute_ssh_command, prepare_shell_command
from api.logging import get_exception_message, get_logger
from api.schemas.policies import Policy
from api.services.coins import CoinService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings

logger = get_logger(__name__)


class ServerManager:
    def __init__(
        self, settings: Settings, setting_service: SettingService, coin_service: CoinService, plugin_registry: PluginRegistry
    ) -> None:
        self.settings = settings
        self.setting_service = setting_service
        self.coin_service = coin_service
        self.plugin_registry = plugin_registry

    async def run_management_command_core(self, func: Callable[[], Awaitable[str]], ok_output: str) -> dict[str, Any]:
        if self.settings.DOCKER_ENV:  # pragma: no cover
            command = await func()
            return self.run_host_output(command, ok_output)
        return {"status": "error", "message": "Not running in docker"}

    async def run_management_command(self, command: str, hook_name: str, ok_output: str) -> dict[str, Any]:
        async def func() -> str:
            await self.plugin_registry.run_hook(hook_name)
            return command

        return await self.run_management_command_core(func, ok_output)

    def run_host(self, command: str, env: dict[str, str] | None = None, disown: bool = True) -> tuple[bool, str | None]:
        if env is None:
            env = {}
        try:
            client = create_ssh_client(self.settings.ssh_settings)
        except Exception as e:
            return False, f"Connection problem: {e}"
        env_vars = " ".join([f"{k}={v}" for k, v in env.items()])
        try:
            output = execute_ssh_command(
                client,
                f'. {self.settings.ssh_settings.bash_profile_script}; cd "$BITCART_BASE_DIRECTORY"; {env_vars} nohup'
                f" {prepare_shell_command(command)}" + (" > /dev/null 2>&1 & disown" if disown else ""),
            )
            if not disown:  # pragma: no cover
                final_out = output[1].read().decode() + "\n" + output[2].read().decode()
                final_out = final_out.strip()
                exitcode = output[1].channel.recv_exit_status()
                if exitcode != 0:
                    return False, final_out
                return True, final_out
        except Exception as e:  # pragma: no cover
            logger.error(get_exception_message(e))
            return False, f"Command execution problem: {e}"
        finally:
            client.close()
        return True, None

    def run_host_output(self, command: str, ok_output: str, env: dict[str, str] | None = None) -> dict[str, Any]:
        if env is None:
            env = {}
        ok, error = self.run_host(command, env=env)
        if ok:
            return {"status": "success", "message": ok_output}
        return {"status": "error", "message": error}

    async def restart_server(self) -> dict[str, Any]:
        return await self.run_management_command("./restart.sh", "server_restart", "Successfully started restart process!")

    async def plugin_reload(self) -> dict[str, Any]:
        return await self.run_management_command("./start.sh", "plugin_reload", "Successfully started plugin reload process!")

    async def update_server(self) -> dict[str, Any]:
        async def func() -> str:
            await self.plugin_registry.run_hook("server_update")
            policy = await self.setting_service.get_setting(Policy)
            return "./install-master.sh" if policy.staging_updates else "./update.sh"

        return await self.run_management_command_core(func, "Successfully started update process!")

    async def cleanup_images(self) -> dict[str, Any]:
        return await self.run_management_command(
            "./cleanup.sh", "server_cleanup_images", "Successfully started cleanup process!"
        )

    async def fetch_currency_info(self, coin: str) -> dict[str, Any]:
        info = {"running": True, "currency": self.coin_service.cryptos[coin].coin_name, "blockchain_height": 0}
        try:
            info.update(await self.coin_service.cryptos[coin].server.getinfo())
        except BitcartBaseError:
            info["running"] = False
        return info

    async def get_syncinfo(self) -> list[dict[str, Any]]:
        coros = [self.fetch_currency_info(coin) for coin in self.coin_service.cryptos]
        return await asyncio.gather(*coros)

    async def test_server_email(self) -> bool:
        policy = await self.setting_service.get_setting(Policy)
        return utils.Email.get_email(policy).check_ping()

    async def get_log_contents(self, log: str) -> str:
        if not self.settings.log_file:
            raise HTTPException(400, "Log file unconfigured")
        try:
            async with aiofiles.open(os.path.join(self.settings.log_dir, log)) as f:
                return (await f.read()).strip()
        except OSError:
            raise HTTPException(404, "This log doesn't exist") from None

    async def delete_log(self, log: str) -> bool:
        if not self.settings.log_file:
            raise HTTPException(400, "Log file unconfigured")
        if log == self.settings.LOG_FILE_NAME:
            raise HTTPException(403, "Forbidden to delete current log file")
        try:
            os.remove(os.path.join(self.settings.log_dir, log))
            return True
        except OSError:
            raise HTTPException(404, "This log doesn't exist") from None

    def log_filter(self, filename: str) -> bool:
        return bool(
            cast(re.Pattern[str], self.settings.log_file_regex).match(filename) and filename != self.settings.LOG_FILE_NAME
        )

    async def get_logs_list(self) -> list[str]:
        if not self.settings.log_file:
            return []
        data = sorted((f for f in os.listdir(self.settings.log_dir) if self.log_filter(f)), reverse=True)
        if os.path.exists(self.settings.log_file):
            data = [cast(str, self.settings.LOG_FILE_NAME)] + data
        return data

    async def cleanup_logs(self) -> dict[str, Any]:
        if not self.settings.log_file:
            return {"status": "error", "message": "Log file unconfigured"}
        for f in os.listdir(self.settings.log_dir):
            if self.log_filter(f):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(self.settings.log_dir, f))
        return {"status": "success", "message": "Successfully cleaned up logs!"}

    async def cleanup_server(self) -> dict[str, Any]:
        data = [await self.cleanup_images(), await self.cleanup_logs()]
        message = ""
        for result in data:
            if result["status"] != "success":
                message += f"{result['message']}\n"
            else:
                return {"status": "success", "message": "Successfully started cleanup process!"}
        return {"status": "error", "message": message}
