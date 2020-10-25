import asyncio
import logging

from sqlalchemy import select

from . import crud, db, models, settings, utils
from .logger import get_logger

logger = get_logger(__name__)

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


async def make_expired_task(invoice, method):  # pragma: no cover
    crud.add_invoice_expiration(invoice)  # to ensure it is the most recent one
    left = invoice.time_left + 1  # to ensure it's already expired at that moment
    if left > 0:
        await asyncio.sleep(left)
    try:
        invoice = await models.Invoice.get(invoice.id)  # refresh data to get new status
        await crud.invoice_add_related(invoice)
    except Exception:
        return  # invoice deleted meantime
    if invoice.status == "Pending":  # to ensure there are no duplicate notifications
        await update_status(invoice, method, "expired")


async def new_payment_handler(instance, event, address, status, status_str, notify=True):
    data = (
        await select([models.Invoice, models.PaymentMethod])
        .where(models.PaymentMethod.invoice_id == models.Invoice.id)
        .where(models.PaymentMethod.currency == instance.coin_name.lower())
        .where(models.PaymentMethod.payment_address == address)
        .where(models.Invoice.status == "Pending")
        .gino.load((models.Invoice, models.PaymentMethod))
        .first()
    )
    if not data:  # received payment but no matching invoice # pragma: no cover
        return
    invoice, method = data
    await update_status(invoice, method, status, notify=notify)


async def invoice_notification(invoice: models.Invoice, status: str):  # pragma: no cover
    await crud.invoice_add_related(invoice)
    await utils.send_ipn(invoice, status)
    if status == "complete":
        logger.info(f"Invoice {invoice.id} complete, sending notifications...")
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
                    product_template = await utils.get_product_template(store, product, quantity)
                    messages.append(product_template)
                    logger.debug(
                        f"Invoice {invoice.id} email notification: rendered product template for product {product_id}:\n"
                        f"{product_template}"
                    )
                store_template = await utils.get_store_template(store, messages)
                logger.debug(f"Invoice {invoice.id} email notification: rendered final template:\n{store_template}")
                utils.send_mail(
                    store,
                    invoice.buyer_email,
                    store_template,
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
        logger.info(f"Updating status of invoice {invoice.id} with payment method {method.currency} to {status}")
        await invoice.update(status=status, discount=method.discount).apply()
        if status == "complete":
            await invoice.update(paid_currency=method.currency).apply()
        await utils.publish_message(invoice.id, {"status": status})
        if notify:  # pragma: no cover
            await invoice_notification(invoice, status)
        return True


async def check_pending(currency):  # pragma: no cover
    try:
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
                    .where(models.WalletxStore.wallet_id == models.Wallet.id)
                    .where(models.WalletxStore.store_id == models.Invoice.store_id)
                    .where(models.Wallet.currency == models.PaymentMethod.currency)
                    .gino.load((models.PaymentMethod, models.Invoice, models.Wallet.xpub))
                    .iterate()
                ):
                    invoice_data = await settings.get_coin(method.currency, xpub).get_request(method.payment_address)
                    if not await update_status(invoice, method, invoice_data["status"]) and invoice.status != "expired":
                        asyncio.ensure_future(make_expired_task(invoice, method))
    except Exception as e:
        logging.error(e)
