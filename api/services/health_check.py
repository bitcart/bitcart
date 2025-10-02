import asyncio

from dishka import AsyncContainer, Scope

from api.logging import get_logger
from api.schemas.policies import Policy
from api.services.crud.stores import StoreService
from api.services.crud.templates import TemplateService
from api.services.notification_manager import NotificationManager
from api.services.server_manager import ServerManager
from api.services.settings import SettingService
from api.utils.common import run_repeated

logger = get_logger(__name__)


class HealthCheckService:
    CHECK_INTERVAL = 60 * 5
    START_DELAY = 60 * 2

    def __init__(self, container: AsyncContainer) -> None:
        self.container = container

    async def start(self) -> None:
        asyncio.create_task(run_repeated(self.check_daemon_health, self.CHECK_INTERVAL, self.START_DELAY))

    async def check_daemon_health(self) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            server_manager = await container.get(ServerManager)
            setting_service = await container.get(SettingService)
            notification_manager = await container.get(NotificationManager)
            template_service = await container.get(TemplateService)
            store_service = await container.get(StoreService)
            syncinfo_data = await server_manager.get_syncinfo()
            failed_daemons = [daemon for daemon in syncinfo_data if not daemon.get("synchronized", False)]
            if not failed_daemons:
                return
            failed_currencies = ", ".join([d["currency"] for d in failed_daemons])
            logger.warning(f"Detected {len(failed_daemons)} failed daemon(s): {failed_currencies}")
            policy = await setting_service.get_setting(Policy)
            store_id = policy.health_check_store_id
            if not store_id:
                logger.info("No health_check_store_id configured in policy, skipping notification")
                return
            store = await store_service.get_or_none(store_id)
            if not store:
                logger.warning(f"Configured health_check_store_id {store_id} not found, skipping notification")
                return
            notification_text = await template_service.get_syncinfo_template(syncinfo_data, failed_daemons)
            success = await notification_manager.notify(store, notification_text)
            if success:
                logger.info(f"Successfully sent health check notification for {len(failed_daemons)} failed daemon(s)")
            else:
                logger.error("Failed to send health check notification")
