from sqlalchemy.orm import selectinload

from api import models
from api.logging import get_exception_message, get_logger
from api.schemas.misc import EmailSettings
from api.schemas.policies import Policy
from api.services.crud.repositories import UserRepository
from api.services.crud.stores import StoreService
from api.services.email import EmailService
from api.services.notification_manager import NotificationManager
from api.services.settings import SettingService

logger = get_logger(__name__)

ALERT_SUBJECT = "Bitcart template problem"


class TemplateAlertService:
    def __init__(
        self,
        notification_manager: NotificationManager,
        email_service: EmailService,
        setting_service: SettingService,
        store_service: StoreService,
        user_repository: UserRepository,
    ) -> None:
        self.notification_manager = notification_manager
        self.email_service = email_service
        self.setting_service = setting_service
        self.store_service = store_service
        self.user_repository = user_repository

    async def send(self, store_id: str | None, text: str) -> None:
        if store_id is None:
            await self._alert_superusers(text)
        else:
            await self._alert_store(store_id, text)

    async def _alert_store(self, store_id: str, text: str) -> None:
        store = await self.store_service.get_or_none(store_id, load=[selectinload(models.Store.user)])
        if store is None:
            return
        if not await self._notify_providers(store, text) and store.user is not None:
            await self._email(store.email_settings, store.user.email, text)

    async def _notify_providers(self, store: models.Store, text: str) -> bool:
        try:
            return (await self.notification_manager.notify(store, text)).sent > 0
        except Exception as e:
            logger.error(f"Store {store.id}: failed to send a template alert: {get_exception_message(e)}")
            return False

    async def _alert_superusers(self, text: str) -> None:
        policy = await self.setting_service.get_setting(Policy)
        for user in await self.user_repository.get_enabled_superusers():
            await self._email(policy.email_settings, user.email, text)

    async def _email(self, settings: EmailSettings, to: str, text: str) -> None:
        if not self.email_service.is_enabled(settings):
            return
        try:
            await self.email_service.send(settings, to, ALERT_SUBJECT, text)
        except Exception as e:
            logger.error(f"Failed to email a template alert: {get_exception_message(e)}")
