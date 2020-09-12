import asyncio
import inspect
from typing import Dict, List, Union

import dramatiq

from . import crud, models, settings, utils

MAX_RETRIES = 3

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


@dramatiq.actor(actor_name="poll_updates", max_retries=MAX_RETRIES)
@settings.run_sync
async def poll_updates(obj: Union[int, models.Invoice], task_wallets: Dict[str, str]):
    obj = await models.Invoice.get(obj)
    if not obj:
        return
    await crud.invoice_add_related(obj)
    if settings.TEST:
        await asyncio.sleep(1)
        await obj.update(status="test").apply()
        await utils.publish_message(obj.id, {"status": "test"})
        return
    payment_methods = await models.PaymentMethod.query.where(models.PaymentMethod.invoice_id == obj.id).gino.all()
    if not payment_methods:
        return
    for ind, method in enumerate(payment_methods):
        payment_methods[ind].coin = settings.get_coin(method.currency, task_wallets[method.currency])
    await process_invoice(obj, task_wallets, payment_methods)


async def process_invoice(
    invoice: models.Invoice, task_wallets: Dict[str, str], payment_methods: List[models.PaymentMethod], notify: bool = True
):
    while not settings.shutdown.is_set():
        for method in payment_methods:
            invoice_data = method.coin.getrequest(method.payment_address)
            invoice_data = await invoice_data if inspect.isawaitable(invoice_data) else invoice_data
            if invoice_data["status"] != "Pending" and invoice_data["status"] != 0:
                status = invoice_data["status"]
                if isinstance(status, int):
                    status = STATUS_MAPPING[status]
                elif isinstance(status, str) and status in STATUS_MAPPING:
                    status = STATUS_MAPPING[status]
                if not status:
                    status = "expired"
                await invoice.update(status=status, discount=method.discount).apply()
                if status == "complete":
                    await invoice.update(paid_currency=method.currency).apply()
                if notify:
                    await invoice_notification(invoice, status)
                return
        await asyncio.sleep(1)
    poll_updates.send_with_options(args=(invoice.id, task_wallets), delay=1000)  # to run on next startup


async def invoice_notification(invoice: models.Invoice, status: str):
    await crud.invoice_add_related(invoice)
    await utils.publish_message(invoice.id, {"status": status})
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


@dramatiq.actor(actor_name="sync_wallet", max_retries=0)
@settings.run_sync
async def sync_wallet(model: Union[int, models.Wallet]):
    test = settings.TEST
    model = await models.Wallet.get(model)
    if not model:
        return
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    await model.update(balance=balance["confirmed"]).apply()
    if test:
        await asyncio.sleep(1)
    await utils.publish_message(model.id, {"status": "success", "balance": balance["confirmed"]})
