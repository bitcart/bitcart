import asyncio
import warnings
from typing import Union, Dict
from starlette.datastructures import CommaSeparatedStrings
from datetime import datetime
import dramatiq

from . import crud, db, models, schemes, settings, utils

MAX_RETRIES = 3

STATUS_MAPPING = {
    0: "Pending",
    3: "complete",
    2: "invalid",
    1: "expired",
    4: "In progress",
    5: "Failed",
}


@dramatiq.actor(actor_name="poll_updates", max_retries=MAX_RETRIES)
@settings.run_sync
async def poll_updates(
    obj: Union[int, models.Invoice], task_wallets: Dict[str, str], test: bool = False
):
    obj = await models.Invoice.get(obj)
    await crud.invoice_add_related(obj)
    product = await models.Product.get(obj.products[0])
    await crud.product_add_related(product)
    payment_methods = await models.PaymentMethod.query.where(
        models.PaymentMethod.invoice_id == obj.id
    ).gino.all()
    discounts = [
        await models.Discount.get(discount_id) for discount_id in product.discounts
    ]
    if not payment_methods:
        return
    for ind, method in enumerate(payment_methods):
        payment_methods[ind].coin = settings.get_coin(
            method.currency, task_wallets[method.currency]
        )
    if test:
        return
    while not settings.shutdown.is_set():
        for method in payment_methods:
            invoice_data = await method.coin.getrequest(method.payment_address)
            if invoice_data["status"] != 0:
                status = STATUS_MAPPING[invoice_data["status"]]
                if not status:
                    status = "expired"
                if status == "complete":
                    for product_id in obj.products:
                        product = await models.Product.get(product_id)
                        store = await models.Store.get(product.store_id)
                        if utils.check_ping(
                            store.email_host,
                            store.email_port,
                            store.email_user,
                            store.email_password,
                            store.email,
                            store.email_use_ssl,
                        ):
                            utils.send_mail(
                                store,
                                obj.buyer_email,
                                utils.get_email_template(store, product),
                            )
                await obj.update(status=status, discount=method.discount).apply()
                await utils.publish_message(obj.id, {"status": status})
                return
        await asyncio.sleep(1)
    poll_updates.send_with_options(
        args=(obj.id, task_wallets, test), delay=1000
    )  # to run on next startup


@dramatiq.actor(actor_name="sync_wallet", max_retries=0)
@settings.run_sync
async def sync_wallet(model: Union[int, models.Wallet]):
    model = await models.Wallet.get(model)
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    await model.update(balance=balance["confirmed"]).apply()
    await utils.publish_message(
        model.id, {"status": "success", "balance": balance["confirmed"]}
    )
