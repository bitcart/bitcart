from api import models
from api.services.crud import CRUDRepository


class PayoutRepository(CRUDRepository[models.Payout]):
    model_type = models.Payout
