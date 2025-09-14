from api import models
from api.services.crud import CRUDRepository


class RefundRepository(CRUDRepository[models.Refund]):
    model_type = models.Refund
