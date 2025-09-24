from sqlalchemy.orm import selectinload

from api import models
from api.services.crud.repository import CRUDRepository


class TemplateRepository(CRUDRepository[models.Template]):
    model_type = models.Template

    LOAD_OPTIONS = [selectinload(models.Template.user)]
