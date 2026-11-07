from typing import Any

from api import models
from api.ext.moneyformat import currency_table
from api.invoices import InvoiceStatus
from api.services.crud.invoices import InvoiceService
from api.services.crud.refunds import RefundService
from api.services.crud.templates import TemplateService
from api.services.management import ManagementService
from api.templates import Template, TemplateAudience, TemplateScope
from api.templates.context import TemplateContextGetter, TemplateTestData, sample_model, with_fields

StoreTestData = TemplateTestData[models.Store]


def chosen_store(data: StoreTestData) -> models.Store:
    return data.owner or sample_model(models.Store)


async def chosen_invoice(data: StoreTestData) -> models.Invoice:
    if data.owner is not None:
        service = await data.container.get(InvoiceService)
        store_id = data.owner.id
        invoice = await service.get_newest(store_id=store_id, status=InvoiceStatus.COMPLETE)
        invoice = invoice or await service.get_newest(store_id=store_id)
        if invoice is not None:
            return invoice
    return sample_model(models.Invoice)


async def chosen_refund_and_invoice(data: StoreTestData) -> tuple[models.Refund, models.Invoice]:
    refund = None
    if data.owner is not None:
        refund_service = await data.container.get(RefundService)
        refund = await refund_service.get_newest(models.Refund.invoice.has(store_id=data.owner.id))
    if refund is None:
        return sample_model(models.Refund), await chosen_invoice(data)
    invoice = await (await data.container.get(InvoiceService)).get(refund.invoice_id)
    return refund, invoice


async def product_test_context(data: TemplateTestData[models.Product]) -> dict[str, Any]:
    product = data.owner or sample_model(models.Product)
    store = product.store or sample_model(models.Store)
    price = currency_table.round_neutral(store.default_currency, product.price)
    return {"store": store, "product": with_fields(product, price=price), "quantity": 1}


async def shop_test_context(data: StoreTestData) -> dict[str, Any]:
    store = chosen_store(data)
    invoice = await chosen_invoice(data)
    template_service = await data.container.get(TemplateService)
    products = [await template_service.preview_product(store, invoice, relation) for relation in invoice.products_associations]
    return {"store": store, "products": products}


async def invoice_test_context(data: StoreTestData) -> dict[str, Any]:
    return {"store": chosen_store(data), "invoice": await chosen_invoice(data)}


async def lightning_description_test_context(data: StoreTestData) -> dict[str, Any]:
    invoice = await chosen_invoice(data)
    return {"store": chosen_store(data), "invoice": invoice, "product": next(iter(invoice.products), None)}


async def merchant_refund_test_context(data: StoreTestData) -> dict[str, Any]:
    refund, invoice = await chosen_refund_and_invoice(data)
    return {"store": chosen_store(data), "invoice": invoice, "refund": refund}


async def customer_refund_test_context(data: StoreTestData) -> dict[str, Any]:
    return {**await merchant_refund_test_context(data), "refund_url": "sample refund_url"}


async def email_code_test_context(data: TemplateTestData[None]) -> dict[str, Any]:
    return {"email": data.user.email, "link": "sample link", "code": "sample code"}


async def syncinfo_test_context(data: TemplateTestData[None]) -> dict[str, Any]:
    daemons = await (await data.container.get(ManagementService)).get_syncinfo()
    return {"syncinfo_data": daemons, "failed_daemons": daemons}


def default_templates() -> list[Template]:
    definitions: list[tuple[str, TemplateScope, TemplateAudience, TemplateContextGetter[Any]]] = [
        ("product", TemplateScope.PRODUCT, TemplateAudience.EXTERNAL, product_test_context),
        ("shop", TemplateScope.STORE, TemplateAudience.EXTERNAL, shop_test_context),
        ("notification", TemplateScope.STORE, TemplateAudience.AUTHOR, invoice_test_context),
        ("lightning_description", TemplateScope.STORE, TemplateAudience.EXTERNAL, lightning_description_test_context),
        ("customer_refund", TemplateScope.STORE, TemplateAudience.EXTERNAL, customer_refund_test_context),
        ("merchant_refund_notify", TemplateScope.STORE, TemplateAudience.AUTHOR, merchant_refund_test_context),
        ("fallback_note", TemplateScope.STORE, TemplateAudience.EXTERNAL, invoice_test_context),
        ("forgotpassword", TemplateScope.GLOBAL, TemplateAudience.EXTERNAL, email_code_test_context),
        ("verifyemail", TemplateScope.GLOBAL, TemplateAudience.EXTERNAL, email_code_test_context),
        ("syncinfo", TemplateScope.GLOBAL, TemplateAudience.AUTHOR, syncinfo_test_context),
    ]
    return [
        Template(name, applicable_to=scope, audience=audience, get_test_context=get_test_context)
        for name, scope, audience, get_test_context in definitions
    ]
