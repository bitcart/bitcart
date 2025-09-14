from api import models
from api.services.crud import CRUDRepository


class PaymentMethodRepository(CRUDRepository[models.PaymentMethod]):
    model_type = models.PaymentMethod


class InvoiceRepository(CRUDRepository[models.Invoice]):
    model_type = models.Invoice
