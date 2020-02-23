import asyncio
from typing import Dict, Union

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
    test = settings.TEST
    obj = await models.Invoice.get(obj)
    await crud.invoice_add_related(obj)
    payment_methods = await models.PaymentMethod.query.where(
        models.PaymentMethod.invoice_id == obj.id
    ).gino.all()
    if not payment_methods:
        return
    for ind, method in enumerate(payment_methods):
        payment_methods[ind].coin = settings.get_coin(
            method.currency, task_wallets[method.currency]
        )
    if test:
        await asyncio.sleep(1)
        await utils.publish_message(obj.id, {"status": "test"})
        return
    while not settings.shutdown.is_set():
        for method in payment_methods:
            invoice_data = await method.coin.getrequest(method.payment_address)
            if invoice_data["status"] != "Pending" and invoice_data["status"] != 0:
                status = invoice_data["status"]
                if isinstance(status, int):
                    status = STATUS_MAPPING[status]
                elif isinstance(status, str) and status in STATUS_MAPPING:
                    status = STATUS_MAPPING[status]
                if not status:
                    status = "expired"
                await obj.update(status=status, discount=method.discount).apply()
                await crud.invoice_add_related(obj)
                await utils.publish_message(obj.id, {"status": status})
                await utils.send_ipn(obj, status)
                if status == "complete" and obj.products:
                    product = await models.Product.get(obj.products[0])
                    store = await models.Store.get(product.store_id)
                    if utils.check_ping(
                        store.email_host,
                        store.email_port,
                        store.email_user,
                        store.email_password,
                        store.email,
                        store.email_use_ssl,
                    ):
                        messages = []
                        for product_id in obj.products:
                            product = await models.Product.get(product_id)
                            relation = (
                                await models.ProductxInvoice.query.where(
                                    models.ProductxInvoice.invoice_id == obj.id
                                )
                                .where(models.ProductxInvoice.product_id == product_id)
                                .gino.first()
                            )
                            quantity = relation.count
                            messages.append(
                                utils.get_product_template(store, product, quantity)
                            )
                        utils.send_mail(
                            store,
                            obj.buyer_email,
                            utils.get_store_template(store, messages),
                        )
                return
        await asyncio.sleep(1)
    poll_updates.send_with_options(
        args=(obj.id, task_wallets), delay=1000
    )  # to run on next startup


@dramatiq.actor(actor_name="sync_wallet", max_retries=0)
@settings.run_sync
async def sync_wallet(model: Union[int, models.Wallet]):
    test = settings.TEST
    model = await models.Wallet.get(model)
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    await model.update(balance=balance["confirmed"]).apply()
    if test:
        await asyncio.sleep(1)
    await utils.publish_message(
        model.id, {"status": "success", "balance": balance["confirmed"]}
    )
