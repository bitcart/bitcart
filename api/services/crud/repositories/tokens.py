from api import models
from api.services.crud.repository import CRUDRepository


class TokenRepository(CRUDRepository[models.Token]):
    model_type = models.Token
