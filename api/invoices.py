from sqlalchemy import select

from . import crud, db, models, settings, utils

STATUS_MAPPING = {
    0: "Pending",
    3: "complete",
    2: "invalid",
    1: "expired",
    4: "In progress",
    5: "Failed",
    "Paid": "complete",
    "Pending": "Pending",
    "Unknown": "invalid",
    "Expired": "expired",
}


async def new_payment_handler(instance, event, address, status, status_str, notify=True):
    invoice, method = (
        await select([models.Invoice, models.PaymentMethod])
        .where(models.PaymentMethod.invoice_id == models.Invoice.id)
        .where(models.PaymentMethod.currency == instance.coin_name.lower())
        .where(models.PaymentMethod.payment_address == address)
        .gino.load((models.Invoice, models.PaymentMethod))
        .first()
    )
    await update_status(invoice, method, status, notify=notify)


async def invoice_notification(invoice: models.Invoice, status: str):  # pragma: no cover
    await crud.invoice_add_related(invoice)
    await utils.send_ipn(invoice, status)
    if status == "complete":
        store = await models.Store.get(invoice.store_id)
        await crud.store_add_related(store)
        await utils.notify(store, await utils.get_notify_template(store, invoice))
        if invoice.products:
            if utils.check_ping(
                store.email_host,
                store.email_port,
                store.email_user,
                store.email_password,
                store.email,
                store.email_use_ssl,
            ):
                messages = []
                for product_id in invoice.products:
                    product = await models.Product.get(product_id)
                    relation = (
                        await models.ProductxInvoice.query.where(models.ProductxInvoice.invoice_id == invoice.id)
                        .where(models.ProductxInvoice.product_id == product_id)
                        .gino.first()
                    )
                    quantity = relation.count
                    messages.append(await utils.get_product_template(store, product, quantity))
                utils.send_mail(
                    store,
                    invoice.buyer_email,
                    await utils.get_store_template(store, messages),
                )


def convert_status(status):  # pragma: no cover
    if isinstance(status, int):
        status = STATUS_MAPPING[status]
    elif isinstance(status, str) and status in STATUS_MAPPING:
        status = STATUS_MAPPING[status]
    if not status:
        status = "expired"
    return status


async def update_status(invoice, method, status, notify=True):
    status = convert_status(status)
    if status != "Pending" and invoice.status != "complete":
        await invoice.update(status=status, discount=method.discount).apply()
        if status == "complete":
            await invoice.update(paid_currency=method.currency).apply()
        await utils.publish_message(invoice.id, {"status": status})
        if notify:  # pragma: no cover
            await invoice_notification(invoice, status)


async def check_pending(currency):  # pragma: no cover
    async with db.db.acquire() as conn:
        async with conn.transaction():
            async for method, invoice, xpub in (
                select(
                    [
                        models.PaymentMethod,
                        models.Invoice,
                        models.Wallet.xpub,
                    ]
                )
                .where(models.PaymentMethod.invoice_id == models.Invoice.id)
                .where(models.Invoice.status == "Pending")
                .where(models.PaymentMethod.currency == currency.lower())
                .gino.load((models.PaymentMethod, models.Invoice, models.Wallet.xpub))
                .iterate()
            ):
                invoice_data = await settings.get_coin(method.currency, xpub).get_request(method.payment_address)
                await update_status(invoice, method, invoice_data["status"])
