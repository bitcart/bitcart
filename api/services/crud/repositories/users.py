from sqlalchemy import select
from sqlalchemy.orm import joinedload

from api import models
from api.services.crud.repository import CRUDRepository


class UserRepository(CRUDRepository[models.User]):
    model_type = models.User

    LOAD_OPTIONS = [joinedload(models.User.tokens)]

    async def get_first_superuser(self) -> models.User | None:
        return (
            await self.session.execute(
                select(models.User).where(models.User.is_superuser.is_(True)).order_by(models.User.created.asc()).limit(1)
            )
        ).scalar()
