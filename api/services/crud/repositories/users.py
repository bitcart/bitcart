from sqlalchemy.orm import joinedload

from api import models
from api.services.crud import CRUDRepository


class UserRepository(CRUDRepository[models.User]):
    model_type = models.User

    LOAD_OPTIONS = [joinedload(models.User.tokens)]
