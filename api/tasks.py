import asyncio
import warnings

from bitcart import BTC

from . import models, schemes, settings

RPC_URL = settings.RPC_URL
RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS

STATUS_MAPPING = {
    0: "Pending",
    3: "complete",
    2: "invalid",
    1: "expired",
    4: "In progress",
    5: "Failed",
}


async def poll_updates(obj: models.Invoice, xpub: str, test: bool = False):
    address = obj.bitcoin_address
    if not address:
        return
    btc = BTC(RPC_URL, xpub=xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    while True:
        invoice_data = await btc.getrequest(address)
        if test:
            return
        if invoice_data["status"] != 0:
            status = STATUS_MAPPING[invoice_data["status"]]
            await obj.update(status=status).apply()
            await settings.layer.group_send(obj.id, {"status": status})
            return
        await asyncio.sleep(1)


async def sync_wallet(model: models.Wallet):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            btc = BTC(RPC_URL, xpub=model.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
            balance = await btc.balance()
        await model.update(balance=balance["confirmed"]).apply()
        await settings.layer.group_send(
            model.id, {"status": "success", "balance": balance["confirmed"]}
        )
    except ValueError:  # wallet loading error
        await model.delete()
        await settings.layer.group_send(model.id, {"status": "error", "balance": 0})
