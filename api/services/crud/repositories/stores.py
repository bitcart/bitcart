from api import models
from api.services.crud import CRUDRepository


class StoreRepository(CRUDRepository[models.Store]):
    model_type = models.Store
