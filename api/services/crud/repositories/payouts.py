from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class PayoutRepository(CRUDRepository[models.Payout]):
    model_type = models.Payout

    LOAD_OPTIONS = [selectinload(models.Payout.wallet), selectinload(models.Payout.store), selectinload(models.Payout.user)]
