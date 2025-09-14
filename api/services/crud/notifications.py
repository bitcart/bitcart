from typing import Any

from sqlalchemy.orm import selectinload

from api import models
from api.db import AsyncSession
from api.services.crud import CRUDService
from api.services.crud.repositories import NotificationRepository
from api.services.notification_manager import NotificationManager
from api.settings import Settings


class NotificationService(CRUDService[models.Notification]):
    repository_type = NotificationRepository

    LOAD_OPTIONS = [selectinload(models.Notification.user)]

    def __init__(self, session: AsyncSession, settings: Settings, notification_manager: NotificationManager) -> None:
        super().__init__(session)
        self.settings = settings
        self.notification_manager = notification_manager

    async def prepare_update(self, data: dict[str, Any], model: models.Notification) -> dict[str, Any]:
        data = await super().prepare_update(data, model)
        if "provider" in data and "data" not in data and model.provider != data["provider"]:
            data["data"] = {}
        return data

    async def load_one(self, model: models.Notification) -> None:
        model.error = False
        model.error = model.provider not in self.notification_manager.notifiers
