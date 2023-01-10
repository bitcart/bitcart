import asyncio
import time

from api import schemes, utils
from api.logger import get_logger
from api.plugins import run_hook

DAY = 60 * 60 * 24
FREQUENCIES = {"daily": DAY, "weekly": 7 * DAY, "monthly": 30 * DAY}


class BackupsManager:
    def __init__(self):
        self.task = None
        self.lock = asyncio.Lock()  # used in the views
        self.logger = get_logger(f"{__name__}::{self.__class__.__name__}")

    async def start(self):
        state = await utils.policies.get_setting(schemes.BackupState)
        backup_policy = await utils.policies.get_setting(schemes.BackupsPolicy)
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

    async def start_backup_task(self, left, backup_policy, fresh=True):
        await self.reset_task()
        if fresh:
            await utils.policies.set_setting(schemes.BackupState(last_run=time.time()))
        self.logger.info(
            f"Scheduling backup task for provider {backup_policy.provider}, frequency {backup_policy.frequency}, left: {left}"
            " seconds"
        )
        self.task = utils.tasks.create_task(self.backup_task(left))

    async def backup_task(self, left):
        left += 1
        if left > 0:
            await asyncio.sleep(left)
        await self.perform_backup()
        backup_policy = await utils.policies.get_setting(schemes.BackupsPolicy)
        if backup_policy.scheduled:
            await self.start_backup_task(FREQUENCIES[backup_policy.frequency], backup_policy)

    async def reset_task(self):
        if self.task is not None:
            self.task.cancel()
            # wait for task cancellation
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def reset(self):
        await self.reset_task()
        await utils.policies.set_setting(schemes.BackupState(last_run=None))

    async def process_new_policy(self, old_policy, new_policy):
        # first, check essential on/off settings
        if old_policy.scheduled and not new_policy.scheduled:
            await self.reset()
        elif not old_policy.scheduled and new_policy.scheduled:
            await self.start()
        # then, check frequency
        elif new_policy.scheduled and old_policy.frequency != new_policy.frequency:
            await self.reset()
            await self.start()

    async def perform_backup(self):
        backup_policy = await utils.policies.get_setting(schemes.BackupsPolicy)
        env_vars = {"BACKUP_PROVIDER": backup_policy.provider}
        env_vars.update(backup_policy.environment_variables)
        self.logger.info("Starting backup, settings:")
        self.logger.info(backup_policy)
        await run_hook("pre_backup", backup_policy)
        exec_command = "./backup.sh"
        self.logger.debug(f"Running {exec_command} with env {env_vars}")
        ok, output = utils.host.run_host(exec_command, env=env_vars, disown=False)
        output = {"status": "success" if ok else "error", "message": output}
        await run_hook("post_backup", backup_policy, output)
        if output["status"] == "error":
            self.logger.error(f"Backup failed with error:\n{output['message']}")
        else:
            self.logger.info("Successfully performed backup!")
        return output


manager = BackupsManager()
