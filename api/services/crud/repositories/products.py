from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class ProductRepository(CRUDRepository[models.Product]):
    model_type = models.Product

    LOAD_OPTIONS = [selectinload(models.Product.discounts), selectinload(models.Product.store)]
