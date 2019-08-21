import asyncio
import warnings

from bitcart_async import BTC

from . import models, schemes, settings

RPC_URL = settings.RPC_URL
RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS


async def poll_updates(obj: models.Invoice, xpub: str):
    address = obj.bitcoin_address
    if not address:
        return
    btc_instance = BTC(RPC_URL, xpub=xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    async with btc_instance as btc:
        while True:
            invoice_data = await btc.getrequest(address)
            if invoice_data["status"] != "Pending":
                if invoice_data["status"] == "Unknown":
                    status = "invalid"
                if invoice_data["status"] == "Expired":
                    status = "expired"
                if invoice_data["status"] == "Paid":
                    status = "complete"
                await obj.update(status=status).apply()
                await settings.layer.group_send(obj.id, {"status": status})
                return
            await asyncio.sleep(1)


async def sync_wallet(model: models.Wallet):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            async with BTC(
                RPC_URL, xpub=model.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS
            ) as btc:
                balance = await btc.balance()
        await model.update(balance=balance["confirmed"]).apply()
        await settings.layer.group_send(
            model.id, {"status": "success", "balance": balance["confirmed"]}
        )
    except ValueError:  # wallet loading error
        await model.delete()
        await settings.layer.group_send(model.id, {"status": "error", "balance": 0})
