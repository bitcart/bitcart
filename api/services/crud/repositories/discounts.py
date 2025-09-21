from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class DiscountRepository(CRUDRepository[models.Discount]):
    model_type = models.Discount

    LOAD_OPTIONS = [selectinload(models.Discount.user)]
