import asyncio
import contextlib
import os
import re
from datetime import datetime, timedelta
from typing import Any, cast

import aiofiles
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException

from api import utils
from api.ext.agent import AgentError
from api.logging import get_logger
from api.schemas.policies import Policy
from api.services.coins import CoinService
from api.services.host_agent import HostAgentService, error_response
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings

logger = get_logger(__name__)


class ManagementService:
    def __init__(
        self,
        settings: Settings,
        setting_service: SettingService,
        coin_service: CoinService,
        plugin_registry: PluginRegistry,
        host_agent: HostAgentService,
    ) -> None:
        self.settings = settings
        self.setting_service = setting_service
        self.coin_service = coin_service
        self.plugin_registry = plugin_registry
        self.host_agent = host_agent

    async def run_job(
        self, command: str, hook_name: str, ok_output: str, args: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            await self.host_agent.require(command)
            await self.plugin_registry.run_hook(hook_name)
            job_id = (await self.host_agent.call(command, args))["job_id"]
        except AgentError as e:
            return error_response(e)
        return {"status": "success", "message": ok_output, "job_id": job_id}

    async def restart_server(self) -> dict[str, Any]:
        return await self.run_job("restart", "server_restart", "Successfully started restart process!")

    async def plugin_reload(self) -> dict[str, Any]:
        return await self.run_job("reload", "plugin_reload", "Successfully started plugin reload process!")

    async def update_server(self) -> dict[str, Any]:
        policy = await self.setting_service.get_setting(Policy)
        channel = "staging" if policy.staging_updates else "stable"
        return await self.run_job("update", "server_update", "Successfully started update process!", {"channel": channel})

    async def cleanup_images(self) -> dict[str, Any]:
        return await self.run_job("cleanup", "server_cleanup_images", "Successfully started cleanup process!")

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

    def _parse_log_date(self, filename: str) -> datetime | None:
        if not self.settings.LOG_FILE_NAME:
            return None
        base, _, ext = self.settings.LOG_FILE_NAME.partition(".")
        if not filename.startswith(base) or not filename.endswith(f".{ext}"):
            return None
        date_str = filename[len(base) : -len(f".{ext}")]
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None

    async def cleanup_old_logs(self, retention_days: int) -> None:
        if not self.settings.log_file:
            return
        cutoff = datetime.now() - timedelta(days=retention_days)
        for f in os.listdir(self.settings.log_dir):
            if not self.log_filter(f):
                continue
            log_date = self._parse_log_date(f)
            if log_date is not None and log_date < cutoff:
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(self.settings.log_dir, f))

    async def cleanup_server(self) -> dict[str, Any]:
        images = await self.cleanup_images()
        logs = await self.cleanup_logs()
        logs_ok = logs["status"] == "success"
        if images["status"] == "success":
            if logs_ok:
                message = "Successfully started cleanup process!"
            else:
                message = f"Started image cleanup. Log cleanup failed: {logs['message']}"
            return {"status": "success", "message": message, "job_id": images["job_id"]}
        images_message = f"Image cleanup did not start: {images['message']}"
        if logs_ok:
            message = f"Cleaned up logs. {images_message}"
        else:
            message = f"{images_message}\nLog cleanup failed: {logs['message']}"
        if "job_id" in images:
            return {"status": "error", "message": message, "job_id": images["job_id"]}
        return {"status": "success" if logs_ok else "error", "message": message}
