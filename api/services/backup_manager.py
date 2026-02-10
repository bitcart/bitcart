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
from api.logging import get_logger
from api.redis import Redis
from api.schemas.misc import BackupState
from api.schemas.policies import BackupsPolicy
from api.schemas.tasks import ProcessNewBackupPolicyMessage
from api.services.management import ManagementService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)

DAY = 60 * 60 * 24
FREQUENCIES = {"daily": DAY, "weekly": 7 * DAY, "monthly": 30 * DAY}


class BackupManager:
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
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            backup_policy = await setting_service.get_setting(BackupsPolicy)
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

    async def perform_backup(self) -> dict[str, Any]:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            backup_policy = await setting_service.get_setting(BackupsPolicy)
        env_vars = {"BACKUP_PROVIDER": backup_policy.provider}
        env_vars.update(backup_policy.environment_variables)
        logger.info("Starting backup, settings:")
        logger.info(backup_policy)  # type: ignore # TODO: ???
        await self.plugin_registry.run_hook("pre_backup", backup_policy)
        exec_command = "./backup.sh"
        logger.debug(f"Running {exec_command} with env {env_vars}")
        async with self.container(scope=Scope.REQUEST) as container:
            management_service = await container.get(ManagementService)
            ok, output_message = management_service.run_host(exec_command, env=env_vars, disown=False)
        output: dict[str, Any] = {"status": "success" if ok else "error", "message": output_message}
        await self.plugin_registry.run_hook("post_backup", backup_policy, output)
        if output["status"] == "error":
            logger.error(f"Backup failed with error:\n{output['message']}")
        else:
            logger.info("Successfully performed backup!")
        return output

    async def download_backup(self, file_id: str) -> FileResponse:
        if self.settings.DOCKER_ENV:  # pragma: no cover
            filename = await self.redis_pool.getdel(f"backups:{file_id}")
            if filename:
                headers = {"Content-Disposition": f"attachment; filename={os.path.basename(filename)}"}
                return FileResponse(os.path.join(self.settings.BACKUPS_DIR, filename), headers=headers)
            raise HTTPException(404, "This backup doesn't exist")
        raise HTTPException(400, "Not running in docker")

    async def restore_backup(self, backup: UploadFile) -> dict[str, Any]:
        async def func() -> str:
            path = os.path.join(self.settings.DATADIR, "backup.tar.gz")
            async with aiofiles.open(path, "wb") as f:
                await f.write(await backup.read())
            await self.plugin_registry.run_hook("restore_backup", path)
            return (
                '. helpers.sh; load_env; ./restore.sh --delete-backup "/var/lib/docker/volumes/$(volume_name'
                ' bitcart_datadir)/_data/backup.tar.gz" '
            )

        async with self.container(scope=Scope.REQUEST) as container:
            management_service = await container.get(ManagementService)
            return await management_service.run_management_command_core(func, "Successfully started restore process!")

    async def perform_backup_for_client(self) -> dict[str, Any]:
        if self.settings.DOCKER_ENV:  # pragma: no cover
            output = await self.perform_backup()
            message = output["message"]
            if output["status"] == "success":
                output["message"] = "Successfully performed backup!"
                lines = message.splitlines()
                for line in lines:
                    if line.startswith("Backed up to"):
                        filename = os.path.basename(line.split()[-1])
                        file_id = utils.common.unique_id()
                        await self.redis_pool.set(f"backups:{file_id}", filename)
                        return {"status": "success", "message": output["message"], "file_id": file_id}
            return output
        return {"status": "error", "message": "Not running in docker"}

    async def set_backup_policies(self, settings: BackupsPolicy) -> BackupsPolicy:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            old_settings = await setting_service.get_setting(BackupsPolicy)
            got = await setting_service.set_setting(settings, write=False)
            await self.broker.publish(
                "process_new_backup_policy", ProcessNewBackupPolicyMessage(old_policy=old_settings, new_policy=got)
            )
            return got
