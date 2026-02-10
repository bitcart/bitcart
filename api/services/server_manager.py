import asyncio

from dishka import AsyncContainer, Scope

from api.logging import get_logger
from api.schemas.policies import Policy
from api.services.management import ManagementService
from api.services.settings import SettingService
from api.utils.common import run_repeated

logger = get_logger(__name__)


class ServerManager:
    LOG_CLEANUP_INTERVAL = 60 * 60 * 24  # daily

    def __init__(self, container: AsyncContainer) -> None:
        self.container = container

    async def start(self) -> None:
        asyncio.create_task(run_repeated(self.cleanup_old_logs, self.LOG_CLEANUP_INTERVAL, 30))

    async def cleanup_old_logs(self) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            management_service = await container.get(ManagementService)
            policy = await setting_service.get_setting(Policy)
            await management_service.cleanup_old_logs(policy.log_retention_days)
