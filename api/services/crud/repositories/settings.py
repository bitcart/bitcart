from sqlalchemy import select

from api import models
from api.services.crud.repository import CRUDRepository


class SettingRepository(CRUDRepository[models.Setting]):
    model_type = models.Setting

    async def get_value(self, name: str) -> str | None:
        return await self.session.scalar(select(models.Setting.value).where(models.Setting.name == name))
