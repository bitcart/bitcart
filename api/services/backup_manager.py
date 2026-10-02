import asyncio
import contextlib
import os
import time
from typing import Any

import aiofiles
from dishka import AsyncContainer, Scope
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from api import utils
from api.ext.agent import AgentError, AgentErrorCode
from api.logging import get_logger
from api.schemas.misc import BackupState, HostAgentJob
from api.schemas.policies import BackupsPolicy
from api.schemas.tasks import ProcessNewBackupPolicyMessage
from api.services.host_agent import HostAgentService, error_response
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)

DAY = 60 * 60 * 24
FREQUENCIES = {"daily": DAY, "weekly": 7 * DAY, "monthly": 30 * DAY}
START_RETRY_INTERVAL = 10 * 60
START_RETRY_SECONDS = 2 * 60 * 60
BACKUP_EXTENSIONS = (".tar.zst.enc", ".tar.gz.enc", ".tar.zst", ".tar.gz")


class BackupManager:
    def __init__(
        self,
        settings: Settings,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
        host_agent: HostAgentService,
        container: AsyncContainer,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.plugin_registry = plugin_registry
        self.host_agent = host_agent
        self.container = container
        self.plugin_registry.register_hook("host_agent_job_finished", self.job_finished)
        self.task: asyncio.Task[Any] | None = None
        self.lock = asyncio.Lock()  # used in the views

    async def start(self) -> None:
        asyncio.create_task(self._start())

    async def _start(self) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            state = await setting_service.get_setting(BackupState)
            backup_policy = await setting_service.get_setting(BackupsPolicy)
        if not backup_policy.scheduled:
            return
        current = time.time()
        fresh = True
        if state.last_run:
            left = FREQUENCIES[backup_policy.frequency] - (current - state.last_run)
            fresh = False
        else:
            left = FREQUENCIES[backup_policy.frequency]
        await self.start_backup_task(left, backup_policy, fresh)

    async def start_backup_task(self, left: float, backup_policy: BackupsPolicy, fresh: bool = True) -> None:
        await self.reset_task()
        if fresh:
            async with self.container(scope=Scope.REQUEST) as container:
                setting_service = await container.get(SettingService)
                await setting_service.set_setting(BackupState(last_run=int(time.time())))
        logger.info(
            "Scheduling backup task",
            provider=backup_policy.provider,
            frequency=backup_policy.frequency,
            left=left,
        )
        self.task = utils.tasks.create_task(self.backup_task(left))

    async def backup_task(self, left: float) -> None:
        left += 1
        if left > 0:
            await asyncio.sleep(left)
        await self.perform_backup()
        backup_policy = await self.get_policy()
        if backup_policy.scheduled:
            await self.start_backup_task(FREQUENCIES[backup_policy.frequency], backup_policy)

    async def reset_task(self) -> None:
        if self.task is not None:
            self.task.cancel()
            # wait for task cancellation
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None

    async def reset(self) -> None:
        await self.reset_task()
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            await setting_service.set_setting(BackupState(last_run=None))

    async def process_new_policy(self, old_policy: BackupsPolicy, new_policy: BackupsPolicy) -> None:
        async with self.lock, self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            await setting_service.set_setting(new_policy)
            # first, check essential on/off settings
            if old_policy.scheduled and not new_policy.scheduled:
                await self.reset()
            elif not old_policy.scheduled and new_policy.scheduled:
                await self.start()
            # then, check frequency
            elif new_policy.scheduled and old_policy.frequency != new_policy.frequency:
                await self.reset()
                await self.start()

    async def get_policy(self) -> BackupsPolicy:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            return await setting_service.get_setting(BackupsPolicy)

    async def start_backup(self, backup_policy: BackupsPolicy) -> str:
        await self.host_agent.require("backup")
        if (running := await self.host_agent.running_job()) is not None:
            raise AgentError(AgentErrorCode.BUSY, "another job is running", job_id=running)
        await self.plugin_registry.run_hook("pre_backup", backup_policy)
        args = {**backup_policy.environment_variables, "BACKUP_PROVIDER": backup_policy.provider}
        try:
            return (await self.host_agent.call("backup", args))["job_id"]
        except AgentError as e:
            await self.backup_failed(backup_policy, error_response(e)["message"])
            raise

    async def backup_failed(self, backup_policy: BackupsPolicy, message: str) -> None:
        await self.plugin_registry.run_hook("post_backup", backup_policy, {"status": "error", "message": message})
        logger.error(f"Backup failed:\n{message}")

    async def job_finished(self, job: HostAgentJob) -> None:
        if job.command != "backup":
            return
        backup_policy = await self.get_policy()
        try:
            status = await self.host_agent.job_status(job.job_id)
        except AgentError as e:
            await self.backup_failed(backup_policy, f"The backup job was lost: {e.message}")
            return
        if status["state"] != "done":
            reason = f" ({status['reason']})" if status.get("reason") else ""
            await self.backup_failed(backup_policy, status["log"] or f"The backup job ended as {status['state']}{reason}")
            return
        await self.plugin_registry.run_hook("post_backup", backup_policy, {"status": "success", "message": status["log"]})
        logger.info("Successfully performed backup")

    async def perform_backup(self) -> None:
        backup_policy = await self.get_policy()
        deadline = time.time() + START_RETRY_SECONDS
        while True:
            try:
                job_id = await self.start_backup(backup_policy)
            except AgentError as e:
                message = error_response(e)["message"]
                retryable = e.code == AgentErrorCode.BUSY or (
                    e.code == AgentErrorCode.UNAVAILABLE and self.host_agent.client.configured
                )
                if retryable and time.time() + START_RETRY_INTERVAL <= deadline:
                    logger.info(f"Backup not started: {message}. Retrying in {START_RETRY_INTERVAL} seconds")
                    await asyncio.sleep(START_RETRY_INTERVAL)
                    continue
                logger.error(f"Scheduled backup not started:\n{message}")
                return
            logger.info(f"Started backup job {job_id}")
            return

    async def download_backup(self, job_id: str) -> FileResponse:
        result = (await self.host_agent.job_status(job_id, "0")).get("result") or {}
        filename = os.path.basename(result.get("filename") or "")
        path = os.path.join(self.settings.BACKUPS_DIR, filename)
        if not os.path.isfile(path):
            raise HTTPException(404, "This backup file doesn't exist")
        return FileResponse(path, filename=filename)

    async def restore_backup(self, backup: UploadFile) -> dict[str, Any]:
        filename = backup.filename or ""
        extension = next((ext for ext in BACKUP_EXTENSIONS if filename.endswith(ext)), None)
        if extension is None:
            return {
                "status": "error",
                "message": "The backup must be a .tar.zst or .tar.gz archive, optionally encrypted (.enc)",
            }
        try:
            await self.host_agent.require("restore")
        except AgentError as e:
            return error_response(e)
        name = f"restore-{utils.common.unique_id()}{extension}"
        path = os.path.join(self.settings.BACKUPS_DIR, name)
        async with aiofiles.open(path, "wb") as f:
            while chunk := await backup.read(1 << 20):
                await f.write(chunk)
        await self.plugin_registry.run_hook("restore_backup", path)
        try:
            job_id = (await self.host_agent.call("restore", {"name": name}))["job_id"]
        except AgentError as e:
            with contextlib.suppress(OSError):
                os.remove(path)
            return error_response(e)
        return {"status": "success", "message": "Successfully started restore process!", "job_id": job_id}

    async def perform_backup_for_client(self) -> dict[str, Any]:
        backup_policy = await self.get_policy()
        try:
            job_id = await self.start_backup(backup_policy)
        except AgentError as e:
            return error_response(e)
        return {"status": "success", "message": "Successfully started backup process!", "job_id": job_id}

    async def set_backup_policies(self, settings: BackupsPolicy) -> BackupsPolicy:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            old_settings = await setting_service.get_setting(BackupsPolicy)
            got = await setting_service.set_setting(settings, write=False)
            await self.broker.publish(
                "process_new_backup_policy", ProcessNewBackupPolicyMessage(old_policy=old_settings, new_policy=got)
            )
            return got
