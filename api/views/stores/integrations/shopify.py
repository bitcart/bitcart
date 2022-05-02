from decimal import Decimal

from fastapi import APIRouter, HTTPException

from api import crud
from api import invoices as invoices_module
from api import models, schemes, utils
from api.ext import shopify as shopify_ext
from api.invoices import InvoiceStatus

router = APIRouter()


@router.get("/{order_id}")
async def get_or_create_shopify_invoice(store_id: str, order_id: str, amount: Decimal, check_only: bool = False):
    store = await utils.database.get_object(models.Store, store_id)
    user = await utils.database.get_object(models.User, store.user_id)
    invoice_order_id = f"{shopify_ext.SHOPIFY_ORDER_PREFIX}{order_id}"
    invoices = (
        await models.Invoice.query.where(models.Invoice.store_id == store.id)
        .where(models.Invoice.order_id == invoice_order_id)
        .gino.all()
    )
    paid_invoice = None
    for invoice in invoices:
        if invoice.status == InvoiceStatus.PENDING:
            return {"invoice_id": invoice.id, "status": invoice.status}
        if invoice.status in invoices_module.PAID_STATUSES:
            paid_invoice = invoice
    if not store.plugin_settings.shopify.shop_name:
        raise HTTPException(404, "Not found")
    client = shopify_ext.get_shopify_client(store)
    order = await client.get_order(order_id)
    if "id" not in order:
        raise HTTPException(404, "Not found")
    if paid_invoice is not None:
        # fix registering after reboot
        if order["financial_status"] == "pending":
            await shopify_ext.update_shopify_status(
                client, order_id, paid_invoice.id, paid_invoice.currency, paid_invoice.price, True
            )
        return {"invoice_id": paid_invoice.id, "status": paid_invoice.status}
    if check_only:
        return {}
    if order["financial_status"] not in ["pending", "partially_paid"]:
        raise HTTPException(404, "Not found")
    final_price = amount if amount < Decimal(order["total_outstanding"]) else Decimal(order["total_outstanding"])
    invoice = await crud.invoices.create_invoice(
        schemes.CreateInvoice(
            price=final_price, store_id=store.id, currency=order["presentment_currency"], order_id=invoice_order_id
        ),
        user=user,
    )
    return {"invoice_id": invoice.id, "status": invoice.status}
