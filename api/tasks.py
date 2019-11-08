import asyncio
import warnings
from typing import Union

import dramatiq

from bitcart import BTC

from . import db, models, schemes, settings

RPC_URL = settings.RPC_URL
RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS
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
async def poll_updates(obj: Union[int, models.Invoice], xpub: str, test: bool = False):
    obj = await models.Invoice.get(obj)
    address = obj.bitcoin_address
    if not address:
        return
    btc = BTC(RPC_URL, xpub=xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    while not settings.shutdown.is_set():
        invoice_data = await btc.getrequest(address)
        if test:
            return
        if invoice_data["status"] != 0:
            status = STATUS_MAPPING[invoice_data["status"]]
            await obj.update(status=status).apply()
            await settings.layer.group_send(obj.id, {"status": status})
            return
        await asyncio.sleep(1)
    poll_updates.send_with_options(
        args=(obj.id, xpub, test), delay=1000
    )  # to run on next startup


@dramatiq.actor(actor_name="sync_wallet", max_retries=0)
@settings.run_sync
async def sync_wallet(model: Union[int, models.Wallet]):
    model = await models.Wallet.get(model)
    btc = BTC(RPC_URL, xpub=model.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    balance = await btc.balance()
    await model.update(balance=balance["confirmed"]).apply()
    await settings.layer.group_send(
        model.id, {"status": "success", "balance": balance["confirmed"]}
    )
