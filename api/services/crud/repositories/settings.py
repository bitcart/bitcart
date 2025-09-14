from api import models
from api.services.crud import CRUDRepository


class SettingRepository(CRUDRepository[models.Setting]):
    model_type = models.Setting
