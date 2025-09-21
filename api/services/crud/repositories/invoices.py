from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class PaymentMethodRepository(CRUDRepository[models.PaymentMethod]):
    model_type = models.PaymentMethod


class InvoiceRepository(CRUDRepository[models.Invoice]):
    model_type = models.Invoice

    LOAD_OPTIONS = [
        selectinload(models.Invoice.products_associations).subqueryload(models.ProductxInvoice.product),
        selectinload(models.Invoice.payments),
        selectinload(models.Invoice.store).subqueryload(models.Store.notifications),
    ]
