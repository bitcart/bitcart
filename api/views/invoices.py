from typing import Optional
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Response, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api import crud, db, events, models, pagination, schemes, settings, utils
from api.ext import export as export_ext
from api.ext.moneyformat import currency_table
from api.invoices import InvoiceStatus
from api.plugins import apply_filters, run_hook

router = APIRouter()


async def get_invoice_noauth(model_id: str):
    item = await utils.database.get_object(models.Invoice, model_id)
    return item


@router.post("/order_id/{order_id:path}", response_model=schemes.DisplayInvoice)
async def get_or_create_invoice_by_order_id(
    order_id: str,
    data: schemes.CreateInvoice,
    user: Optional[models.User] = Security(utils.authorization.optional_auth_dependency, scopes=["invoice_management"]),
):
    item = await utils.database.get_object(
        models.Invoice,
        order_id,
        custom_query=models.Invoice.query.where(models.Invoice.order_id == order_id)
        .where(models.Invoice.store_id == data.store_id)
        .where(models.Invoice.status != InvoiceStatus.EXPIRED),
        raise_exception=False,
    )
    if not item:
        data.order_id = order_id
        item = await crud.invoices.create_invoice(data, user)
    return item


@router.get("/export")
async def export_invoices(
    response: Response,
    pagination: pagination.Pagination = Depends(),
    export_format: str = "json",
    add_payments: bool = False,
    all_users: bool = False,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["invoice_management"]),
):
    if all_users and not user.is_superuser:
        raise HTTPException(403, "Not enough permissions")
    # always full list for export
    pagination.limit = -1
    pagination.offset = 0
    query = pagination.get_base_query(models.Invoice).where(models.Invoice.status == InvoiceStatus.COMPLETE)
    if not all_users:
        query = query.where(models.Invoice.user_id == user.id)
    data = await pagination.get_list(query)
    await utils.database.postprocess_func(data)
    data = list(export_ext.db_to_json(data, add_payments))
    now = utils.time.now()
    filename = now.strftime(f"bitcartcc-export-%Y%m%d-%H%M%S.{export_format}")
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    response.headers.update(headers)
    if export_format == "json":
        return data
    else:
        return StreamingResponse(
            iter([export_ext.json_to_csv(data).getvalue()]),
            media_type="application/csv",
            headers=headers,
        )


@router.patch("/{model_id}/customer", response_model=schemes.DisplayInvoice)
async def update_invoice(
    model_id: str,
    data: schemes.CustomerUpdateData,
):
    item = await utils.database.get_object(models.Invoice, model_id)
    kwargs = {}
    for field, value in data:
        if not getattr(item, field) and value:
            kwargs[field] = value
    if kwargs:
        await run_hook("invoice_customer_update", item, kwargs)
        await utils.database.modify_object(item, kwargs)
    return item


@router.patch("/{model_id}/details")
async def update_payment_details(
    model_id: str,
    data: schemes.MethodUpdateData,
):  # pragma: no cover
    item = await utils.database.get_object(models.Invoice, model_id)
    if item.status != InvoiceStatus.PENDING:
        raise HTTPException(422, "Can't update details for paid invoice")
    found_payment = None
    for payment in item.payments:
        if payment["id"] == data.id:
            found_payment = payment
            break
    if found_payment is None:
        raise HTTPException(404, "No such payment method found")
    if found_payment["user_address"] is not None:
        raise HTTPException(422, "Can't update payment address once set")
    fetch_data = (
        await select([models.PaymentMethod, models.Wallet])
        .where(models.Wallet.id == models.PaymentMethod.wallet_id)
        .where(models.PaymentMethod.id == payment["id"])
        .gino.load((models.PaymentMethod, models.Wallet))
        .first()
    )
    if not fetch_data:
        raise HTTPException(404, "No such payment method found")
    method, wallet = fetch_data
    coin = await settings.settings.get_coin(
        method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
    )
    try:
        data.address = await coin.server.normalizeaddress(data.address)
    except Exception:
        raise HTTPException(422, "Invalid address")
    if not await coin.server.setrequestaddress(method.lookup_field, data.address):
        raise HTTPException(422, "Invalid address")
    await run_hook("invoice_payment_address_set", item, method, data.address)
    await method.update(user_address=data.address).apply()
    return True


@router.post("/{model_id}/refunds", response_model=schemes.Refund)
async def refund_invoice(
    data: schemes.RefundData,
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["invoice_management", "payout_management"]),
):
    invoice = await utils.database.get_object(models.Invoice, model_id, user)
    if not invoice.paid_currency:
        raise HTTPException(422, "Can't refund unpaid invoice")
    payment = crud.invoices.match_payment(invoice.payments, invoice.paid_currency)
    refund = await utils.database.create_object(
        models.Refund,
        schemes.CreateRefund(
            amount=data.amount, currency=data.currency, wallet_id=payment["wallet_id"], invoice_id=invoice.id
        ),
        user,
    )
    if data.send_email and invoice.buyer_email:
        store = await utils.database.get_object(models.Store, invoice.store_id)
        if utils.email.check_store_ping(store):
            refund_url = urljoin(data.admin_host, f"/refunds/{refund.id}")
            refund.amount = currency_table.normalize(refund.currency, refund.amount)
            refund_template = await apply_filters(
                "refund_customer_text",
                await utils.templates.get_customer_refund_template(store, invoice, refund, refund_url),
                store,
                invoice,
                refund,
                refund_url,
            )
            utils.email.send_store_email(store, invoice.buyer_email, refund_template, f"Refund for invoice {invoice.id}")
    return refund


@router.get("/refunds/{refund_id}", response_model=schemes.Refund)
async def get_refund(refund_id: str):
    refund = await utils.database.get_object(models.Refund, refund_id)
    payout_status = None
    tx_hash = None
    wallet_currency = None
    if refund.payout_id:
        payout = await utils.database.get_object(models.Payout, refund.payout_id)
        payout_status = payout.status
        tx_hash = payout.tx_hash
        wallet_currency = payout.wallet_currency
    refund.payout_status = payout_status
    refund.tx_hash = tx_hash
    refund.wallet_currency = wallet_currency
    return refund


@router.post("/refunds/{refund_id}/submit", response_model=schemes.Refund)
async def submit_refund(refund_id: str, data: schemes.SubmitRefundData):
    async with db.db.transaction():
        refund = await utils.database.get_object(models.Refund, refund_id, atomic_update=True)
        if refund.payout_id:
            raise HTTPException(422, "Refund already submitted")
        invoice = await utils.database.get_object(models.Invoice, refund.invoice_id)
        payout = await utils.database.create_object(
            models.Payout,
            schemes.CreatePayout(
                amount=refund.amount,
                currency=refund.currency,
                destination=data.destination,
                store_id=invoice.store_id,
                wallet_id=refund.wallet_id,
            ),
            user_id=refund.user_id,
        )
        await refund.update(payout_id=payout.id, destination=data.destination).apply()
        refund.payout_status = payout.status
        refund.tx_hash = payout.tx_hash
        refund.wallet_currency = payout.wallet_currency
        store = await utils.database.get_object(models.Store, invoice.store_id)
        refund.amount = currency_table.normalize(refund.currency, refund.amount)
        await events.event_handler.publish(
            "send_notification",
            {
                "store_id": invoice.store_id,
                "text": await utils.templates.get_merchant_refund_notify_template(store, invoice, refund),
            },
        )
        return refund


utils.routing.ModelView.register(
    router,
    "/",
    models.Invoice,
    schemes.Invoice,
    schemes.CreateInvoice,
    schemes.DisplayInvoice,
    custom_methods={
        "post": crud.invoices.create_invoice,
        "batch_action": crud.invoices.batch_invoice_action,
    },
    request_handlers={"get_one": get_invoice_noauth},
    post_auth=False,
    scopes=["invoice_management"],
    custom_commands={"mark_complete": crud.invoices.mark_invoice_complete, "mark_invalid": crud.invoices.mark_invoice_invalid},
)
