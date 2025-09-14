from api import models
from api.services.crud import CRUDRepository


class TemplateRepository(CRUDRepository[models.Template]):
    model_type = models.Template
