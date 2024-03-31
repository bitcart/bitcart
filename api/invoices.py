import asyncio
from decimal import Decimal

from bitcart import errors
from sqlalchemy import or_, select

from api import constants, crud, events, models, settings, utils
from api.ext import payouts as payout_ext
from api.ext.moneyformat import currency_table
from api.logger import get_logger
from api.plugins import apply_filters, run_hook
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
    REFUNDED = "refunded"


class InvoiceExceptionStatus:
    NONE = "none"
    PAID_PARTIAL = "paid_partial"
    PAID_OVER = "paid_over"
    FAILED_CONFIRM = "failed_confirm"


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
            async for method, invoice, wallet in (
                get_pending_invoices_query(currency, statuses=statuses)
                .gino.load((models.PaymentMethod, models.Invoice, models.Wallet))
                .iterate()
            ):
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
        await run_hook("invoice_expired", invoice)


async def process_electrum_status(invoice, method, wallet, electrum_status, tx_hashes, sent_amount):
    electrum_status = convert_status(electrum_status)
    if invoice.status not in DEFAULT_PENDING_STATUSES:  # double-check
        return
    if electrum_status == InvoiceStatus.PENDING and sent_amount > 0:
        await update_status(invoice, InvoiceStatus.PENDING, method, tx_hashes, sent_amount)
    if electrum_status == InvoiceStatus.UNCONFIRMED:  # for on-chain invoices only
        await update_status(invoice, InvoiceStatus.PAID, method, tx_hashes, sent_amount)
        await update_confirmations(
            invoice, method, confirmations=0, tx_hashes=tx_hashes, sent_amount=sent_amount
        )  # to trigger complete for stores accepting 0-conf
    if electrum_status == InvoiceStatus.COMPLETE:  # for paid lightning invoices or confirmed on-chain invoices
        if method.lightning:
            await update_status(invoice, InvoiceStatus.COMPLETE, method, tx_hashes, sent_amount)
        else:
            await update_confirmations(invoice, method, await get_confirmations(method, wallet), tx_hashes, sent_amount)
    return True


async def new_payment_handler(
    instance, event, address, status, status_str, tx_hashes=[], sent_amount=Decimal(0), contract=None
):
    with log_errors():
        sent_amount = Decimal(sent_amount)
        query = get_pending_invoices_query(instance.coin_name.lower()).where(models.PaymentMethod.lookup_field == address)
        if contract:
            query = query.where(models.PaymentMethod.contract == contract)
        data = await query.gino.load((models.PaymentMethod, models.Invoice, models.Wallet)).first()
        if not data:  # received payment but no matching invoice
            return
        method, invoice, wallet = data
        await invoice.load_data()
        await run_hook("new_payment", invoice, method, wallet, status, status_str, tx_hashes, sent_amount)
        await process_electrum_status(invoice, method, wallet, status, tx_hashes, sent_amount)


async def update_confirmations(invoice, method, confirmations, tx_hashes=[], sent_amount=Decimal(0)):
    await method.update(confirmations=confirmations).apply()
    store = await utils.database.get_object(models.Store, invoice.store_id)
    status = invoice.status
    if confirmations >= 1:
        status = InvoiceStatus.CONFIRMED
    if confirmations >= store.checkout_settings.transaction_speed:
        status = InvoiceStatus.COMPLETE
    await update_status(invoice, status, method, tx_hashes, sent_amount)


async def get_confirmations(method, wallet):
    coin = await settings.settings.get_coin(
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
            if invoice.status != InvoiceStatus.CONFIRMED or method.id != invoice.payment_id or method.lightning:
                continue
            await invoice.load_data()
            confirmations = await get_confirmations(method, wallet)
            if confirmations != method.confirmations:
                coros.append(update_confirmations(invoice, method, confirmations, invoice.tx_hashes, invoice.sent_amount))
    coros.append(run_hook("new_block", instance.coin_name.lower(), height))
    # NOTE: if another operation in progress exception occurs, make it await one by one
    await asyncio.gather(*coros)


async def invoice_notification(invoice: models.Invoice, status: str):
    await run_hook("invoice_status", invoice, status)
    await utils.notifications.send_ipn(invoice, status)
    if status == InvoiceStatus.COMPLETE:
        logger.info(f"Invoice {invoice.id} complete, sending notifications...")
        await run_hook("invoice_complete", invoice)
        store = await utils.database.get_object(models.Store, invoice.store_id)
        await utils.notifications.notify(store, await utils.templates.get_notify_template(store, invoice))
        if invoice.products and (email_obj := utils.StoreEmail.get_email(store)).is_enabled():
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
            store_template = await apply_filters(
                "email_notification_text",
                await utils.templates.get_store_template(store, messages),
                invoice,
                store,
                products,
            )
            logger.debug(f"Invoice {invoice.id} email notification: rendered final template:\n{store_template}")
            await run_hook("invoice_email", invoice, store_template)
            email_obj.send_mail(invoice.buyer_email, store_template)


async def process_notifications(invoice):
    await events.event_handler.publish("invoice_status", {"id": invoice.id, "status": invoice.status})
    await utils.redis.publish_message(
        f"invoice:{invoice.id}",
        {
            "status": invoice.status,
            "exception_status": invoice.exception_status,
            "sent_amount": currency_table.format_decimal(
                "",
                invoice.sent_amount,
                divisibility=crud.invoices.find_sent_amount_divisibility(invoice.id, invoice.payments, invoice.payment_id),
            ),
            "paid_currency": invoice.paid_currency,
        },
    )
    await invoice_notification(invoice, invoice.status)


async def update_stock_levels(invoice):
    quantities = (
        await select([models.Product.quantity, models.ProductxInvoice.product_id, models.ProductxInvoice.count])
        .where(models.ProductxInvoice.product_id == models.Product.id)
        .where(models.ProductxInvoice.invoice_id == invoice.id)
        .gino.all()
    )
    async with utils.database.iterate_helper():  # transaction (ACID)
        for product_quantity, product_id, quantity in quantities:
            if product_quantity == -1:  # unlimited quantity
                continue
            await models.Product.update.values(quantity=max(0, product_quantity - quantity)).where(
                models.Product.id == product_id
            ).gino.status()


async def update_status(invoice, status, method=None, tx_hashes=[], sent_amount=Decimal(0), set_exception_status=None):
    if status == InvoiceStatus.PENDING and invoice.status == InvoiceStatus.PENDING and method and sent_amount > 0:
        full_method_name = method.get_name()
        if True:
            await invoice.update(
                paid_currency=full_method_name,
                payment_id=method.id,
                discount=method.discount,
                tx_hashes=tx_hashes,
                sent_amount=sent_amount,
                exception_status=InvoiceExceptionStatus.PAID_PARTIAL,
            ).apply()
            await process_notifications(invoice)

    if (
        invoice.status != status
        and status != InvoiceStatus.PENDING
        and (invoice.status != InvoiceStatus.COMPLETE or status == InvoiceStatus.REFUNDED)
    ):
        log_text = f"Updating status of invoice {invoice.id}"
        if method:
            full_method_name = method.get_name()
            if status in [
                InvoiceStatus.PAID,
                InvoiceStatus.CONFIRMED,
                InvoiceStatus.COMPLETE,
            ]:
                exception_status = (
                    InvoiceExceptionStatus.NONE
                    if sent_amount == method.amount or method.lightning
                    else InvoiceExceptionStatus.PAID_OVER
                )
                kwargs = dict(
                    paid_currency=full_method_name,
                    payment_id=method.id,
                    discount=method.discount,
                    tx_hashes=tx_hashes,
                    sent_amount=sent_amount,
                    exception_status=exception_status,
                )
                if not invoice.paid_date:
                    kwargs["paid_date"] = utils.time.now()
                await invoice.update(**kwargs).apply()
            log_text += f" with payment method {full_method_name}"
        logger.info(f"{log_text} to {status}")
        kwargs = {"status": status}
        if set_exception_status:
            kwargs["exception_status"] = set_exception_status
        await invoice.update(**kwargs).apply()
        if status == InvoiceStatus.COMPLETE:
            await update_stock_levels(invoice)
        await process_notifications(invoice)
        return True


async def create_expired_tasks():
    with log_errors():
        async with utils.database.iterate_helper():
            async for invoice in models.Invoice.query.where(models.Invoice.status == InvoiceStatus.PENDING).gino.iterate():
                with log_errors():
                    asyncio.ensure_future(make_expired_task(invoice))


async def check_pending(currency, process_func=process_electrum_status):
    coros = []
    coros.append(payout_ext.process_new_block(currency.lower()))
    async for method, invoice, wallet in iterate_pending_invoices(currency):
        with log_errors():  # issues processing one item
            if invoice.status == InvoiceStatus.EXPIRED:
                continue
            coin = await settings.settings.get_coin(
                method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
            )
            try:
                if method.lightning:
                    invoice_data = await coin.get_invoice(method.lookup_field)
                else:
                    invoice_data = await coin.get_request(method.lookup_field)
            except errors.RequestNotFoundError:  # invoice dropped from mempool
                await update_status(invoice, InvoiceStatus.INVALID, set_exception_status=InvoiceExceptionStatus.FAILED_CONFIRM)
                continue
            coros.append(
                process_func(
                    invoice,
                    method,
                    wallet,
                    invoice_data["status"],
                    invoice_data.get("tx_hashes", []),
                    Decimal(invoice_data.get("sent_amount", 0)),
                )
            )
    await asyncio.gather(*coros)
