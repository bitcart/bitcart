from sqlalchemy.orm import selectinload

from api import models
from api.services.crud.repository import CRUDRepository


class StoreRepository(CRUDRepository[models.Store]):
    model_type = models.Store

    LOAD_OPTIONS = [selectinload(models.Store.wallets), selectinload(models.Store.notifications)]
