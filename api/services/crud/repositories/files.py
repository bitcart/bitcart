from api import models
from api.services.crud.repository import CRUDRepository


class FileRepository(CRUDRepository[models.File]):
    model_type = models.File
