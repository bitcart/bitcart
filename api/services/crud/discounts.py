from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDService
from api.services.crud.repositories import DiscountRepository


class DiscountService(CRUDService[models.Discount]):
    repository_type = DiscountRepository

    LOAD_OPTIONS = [selectinload(models.Discount.user)]
