from sqlalchemy import select
from sqlalchemy.orm import joinedload

from api import models
from api.services.crud.repository import CRUDRepository


class UserRepository(CRUDRepository[models.User]):
    model_type = models.User

    LOAD_OPTIONS = [joinedload(models.User.tokens)]

    async def get_enabled_superusers(self) -> list[models.User]:
        return await self.get_many(is_superuser=True, is_enabled=True, load=[])

    async def get_first_superuser(self) -> models.User | None:
        return (
            await self.session.execute(
                select(models.User).where(models.User.is_superuser.is_(True)).order_by(models.User.created.asc()).limit(1)
            )
        ).scalar()

    async def get_allowed_internal_hosts(self, user_id: str | None) -> list[str]:
        if user_id is None:
            return []
        query = select(models.User.allowed_internal_hosts).where(models.User.id == user_id)
        return await self.session.scalar(query) or []
