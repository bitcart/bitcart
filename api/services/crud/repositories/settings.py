from api import models
from api.services.crud.repository import CRUDRepository


class SettingRepository(CRUDRepository[models.Setting]):
    model_type = models.Setting
