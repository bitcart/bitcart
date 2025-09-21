from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class RefundRepository(CRUDRepository[models.Refund]):
    model_type = models.Refund

    LOAD_OPTIONS = [selectinload(models.Refund.payout).subqueryload(models.Payout.wallet)]
