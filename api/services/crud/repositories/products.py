from api import models
from api.services.crud import CRUDRepository


class ProductRepository(CRUDRepository[models.Product]):
    model_type = models.Product
