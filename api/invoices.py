import asyncio

from sqlalchemy import or_, select

from api import constants, events, models, settings, utils
from api.ext import payouts as payout_ext
from api.ext.moneyformat import currency_table
from api.logger import get_logger
from api.utils.logging import log_errors

logger = get_logger(__name__)


class InvoiceStatus:
    PENDING = "pending"
    PAID = "paid"
    UNCONFIRMED = "unconfirmed"  # equals to paid, electrum status
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    INVALID = "invalid"
    COMPLETE = "complete"


# TODO: move it to daemon somehow
STATUS_MAPPING = {
    # electrum integer statuses
    0: InvoiceStatus.PENDING,
    1: InvoiceStatus.EXPIRED,
    2: InvoiceStatus.INVALID,
    3: InvoiceStatus.COMPLETE,
    4: "In progress",
    5: "Failed",
    6: "routing",
    7: InvoiceStatus.UNCONFIRMED,
    # for pending checks on reboot we also maintain string versions of those statuses
    "Pending": InvoiceStatus.PENDING,  # electrum < 4.1, electron-cash
    "Unpaid": InvoiceStatus.PENDING,  # electrum 4.1
    "Paid": InvoiceStatus.COMPLETE,
    "Unknown": InvoiceStatus.INVALID,
    "Expired": InvoiceStatus.EXPIRED,
    "Unconfirmed": InvoiceStatus.UNCONFIRMED,
}

DEFAULT_PENDING_STATUSES = [InvoiceStatus.PENDING, InvoiceStatus.PAID]
PAID_STATUSES = [InvoiceStatus.PAID, InvoiceStatus.CONFIRMED, InvoiceStatus.COMPLETE]
FAILED_STATUSES = [InvoiceStatus.EXPIRED, InvoiceStatus.INVALID]


def convert_status(status):
    if isinstance(status, int):
        status = STATUS_MAPPING[status]
    elif isinstance(status, str) and status in STATUS_MAPPING:
        status = STATUS_MAPPING[status]
    if not status:
        status = InvoiceStatus.EXPIRED
    return status


def get_pending_invoice_statuses(statuses=None):
    statuses = statuses or DEFAULT_PENDING_STATUSES
    return or_(
        *(models.Invoice.status == status for status in statuses),
    )


def get_pending_invoices_query(currency, statuses=None):
    return (
        select(
            [
                models.PaymentMethod,
                models.Invoice,
                models.Wallet,
            ]
        )
        .where(models.PaymentMethod.invoice_id == models.Invoice.id)
        .where(models.PaymentMethod.wallet_id == models.Wallet.id)
        .where(get_pending_invoice_statuses(statuses=statuses))
        .where(models.PaymentMethod.currency == currency.lower())
        .where(models.Wallet.currency == models.PaymentMethod.currency)
        .order_by(models.PaymentMethod.created)
    )


async def iterate_pending_invoices(currency, statuses=None):
    with log_errors():  # connection issues
        async with utils.database.iterate_helper():
            async for method, invoice, wallet in get_pending_invoices_query(currency, statuses=statuses).gino.load(
                (models.PaymentMethod, models.Invoice, models.Wallet)
            ).iterate():
                await invoice.load_data()
                yield method, invoice, wallet


async def make_expired_task(invoice):
    invoice.add_invoice_expiration()  # to ensure it is the most recent one
    left = invoice.time_left + 1  # to ensure it's already expired at that moment
    if left > 0:
        await asyncio.sleep(left)
    try:
        invoice = await utils.database.get_object(models.Invoice, invoice.id)  # refresh data to get new status
    except Exception:
        return  # invoice deleted meantime
    if invoice.status == InvoiceStatus.PENDING:  # to ensure there are no duplicate notifications
        await update_status(invoice, InvoiceStatus.EXPIRED)


async def process_electrum_status(invoice, method, wallet, electrum_status, tx_hashes):
    electrum_status = convert_status(electrum_status)
    if invoice.status not in DEFAULT_PENDING_STATUSES:  # double-check
        return
    if electrum_status == InvoiceStatus.UNCONFIRMED:  # for on-chain invoices only
        await update_status(invoice, InvoiceStatus.PAID, method, tx_hashes)
        await update_confirmations(
            invoice, method, confirmations=0, tx_hashes=tx_hashes
        )  # to trigger complete for stores accepting 0-conf
    if electrum_status == InvoiceStatus.COMPLETE:  # for paid lightning invoices or confirmed on-chain invoices
        if method.lightning:
            await update_status(invoice, InvoiceStatus.COMPLETE, method, tx_hashes)
        else:
            await update_confirmations(invoice, method, await get_confirmations(method, wallet), tx_hashes)
    return True


async def new_payment_handler(instance, event, address, status, status_str, tx_hashes=[], contract=None):
    with log_errors():
        query = get_pending_invoices_query(instance.coin_name.lower()).where(models.PaymentMethod.lookup_field == address)
        if contract:
            query = query.where(models.PaymentMethod.contract == contract)
        data = await query.gino.load((models.PaymentMethod, models.Invoice, models.Wallet)).first()
        if not data:  # received payment but no matching invoice
            return
        method, invoice, wallet = data
        await invoice.load_data()
        await process_electrum_status(invoice, method, wallet, status, tx_hashes)


async def update_confirmations(invoice, method, confirmations, tx_hashes=[]):
    await method.update(confirmations=confirmations).apply()
    store = await utils.database.get_object(models.Store, invoice.store_id)
    status = invoice.status
    if confirmations >= 1:
        status = InvoiceStatus.CONFIRMED
    if confirmations >= store.checkout_settings.transaction_speed:
        status = InvoiceStatus.COMPLETE
    await update_status(invoice, status, method, tx_hashes)


async def get_confirmations(method, wallet):
    coin = settings.settings.get_coin(
        method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
    )
    invoice_data = await coin.get_request(method.lookup_field)
    return min(
        constants.MAX_CONFIRMATION_WATCH, invoice_data.get("confirmations", 0)
    )  # don't store arbitrary number of confirmations


async def new_block_handler(instance, event, height):
    coros = []
    coros.append(payout_ext.process_new_block(instance.coin_name.lower()))
    async for method, invoice, wallet in iterate_pending_invoices(
        instance.coin_name.lower(), statuses=[InvoiceStatus.CONFIRMED]
    ):
        with log_errors():  # issues processing one item
            if invoice.status != InvoiceStatus.CONFIRMED or method.get_name() != invoice.paid_currency or method.lightning:
                continue
            await invoice.load_data()
            confirmations = await get_confirmations(method, wallet)
            if confirmations != method.confirmations:
                coros.append(update_confirmations(invoice, method, confirmations))
    # NOTE: if another operation in progress exception occurs, make it await one by one
    await asyncio.gather(*coros)


async def invoice_notification(invoice: models.Invoice, status: str):
    await utils.notifications.send_ipn(invoice, status)
    if status == InvoiceStatus.COMPLETE:
        logger.info(f"Invoice {invoice.id} complete, sending notifications...")
        store = await utils.database.get_object(models.Store, invoice.store_id)
        await utils.notifications.notify(store, await utils.templates.get_notify_template(store, invoice))
        if invoice.products:
            if utils.email.check_ping(
                store.email_host,
                store.email_port,
                store.email_user,
                store.email_password,
                store.email,
                store.email_use_ssl,
            ):
                messages = []
                products = await utils.database.get_objects(models.Product, invoice.products)
                for product in products:
                    product.price = currency_table.normalize(
                        invoice.currency, product.price
                    )  # to be formatted correctly in emails
                    relation = (
                        await models.ProductxInvoice.query.where(models.ProductxInvoice.invoice_id == invoice.id)
                        .where(models.ProductxInvoice.product_id == product.id)
                        .gino.first()
                    )
                    quantity = relation.count
                    product_template = await utils.templates.get_product_template(store, product, quantity)
                    messages.append(product_template)
                    logger.debug(
                        f"Invoice {invoice.id} email notification: rendered product template for product {product.id}:\n"
                        f"{product_template}"
                    )
                store_template = await utils.templates.get_store_template(store, messages)
                logger.debug(f"Invoice {invoice.id} email notification: rendered final template:\n{store_template}")
                utils.email.send_mail(
                    store,
                    invoice.buyer_email,
                    store_template,
                )


async def update_status(invoice, status, method=None, tx_hashes=[]):
    if invoice.status != status and status != InvoiceStatus.PENDING and invoice.status != InvoiceStatus.COMPLETE:
        log_text = f"Updating status of invoice {invoice.id}"
        if method:
            full_method_name = method.get_name()
            if not invoice.paid_currency and status in [InvoiceStatus.PAID, InvoiceStatus.CONFIRMED, InvoiceStatus.COMPLETE]:
                await invoice.update(paid_currency=full_method_name, discount=method.discount, tx_hashes=tx_hashes).apply()
            log_text += f" with payment method {full_method_name}"
        logger.info(f"{log_text} to {status}")
        await invoice.update(status=status).apply()
        await events.event_handler.publish("invoice_status", {"id": invoice.id, "status": status})
        await utils.redis.publish_message(f"invoice:{invoice.id}", {"status": status})
        await invoice_notification(invoice, status)
        return True


async def create_expired_tasks():
    with log_errors():
        async with utils.database.iterate_helper():
            async for invoice in models.Invoice.query.where(models.Invoice.status == InvoiceStatus.PENDING).gino.iterate():
                with log_errors():
                    asyncio.ensure_future(make_expired_task(invoice))


async def check_pending(currency):
    coros = []
    coros.append(payout_ext.process_new_block(currency.lower()))
    async for method, invoice, wallet in iterate_pending_invoices(currency):
        with log_errors():  # issues processing one item
            if invoice.status == InvoiceStatus.EXPIRED:
                continue
            coin = settings.settings.get_coin(
                method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
            )
            if method.lightning:
                invoice_data = await coin.get_invoice(method.lookup_field)
            else:
                invoice_data = await coin.get_request(method.lookup_field)
            coros.append(
                process_electrum_status(invoice, method, wallet, invoice_data["status"], invoice_data.get("tx_hashes", []))
            )
    await asyncio.gather(*coros)
