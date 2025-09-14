from api import models
from api.services.crud import CRUDRepository


class TokenRepository(CRUDRepository[models.Token]):
    model_type = models.Token
