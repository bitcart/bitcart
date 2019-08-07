from bitcart_async import BTC
from . import models, schemes, settings

RPC_URL = settings.RPC_URL
RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS


async def poll_updates(invoice_id: int):
    obj = await models.Invoice.get(invoice_id)
    address = obj.bitcoin_address
    if not address:
        return
    btc_instance = BTC(RPC_URL, xpub=obj.products.all()[0].store.wallet.xpub,
                       rpc_user=RPC_USER, rpc_pass=RPC_PASS)


async def sync_wallet(wallet_id: int):
    model = await models.Wallet.get(wallet_id)
    try:
        balance = await BTC(
            RPC_URL,
            xpub=model.xpub,
            rpc_user=RPC_USER,
            rpc_pass=RPC_PASS).balance()
        await model.update(balance=balance["confirmed"]).apply()
    except ValueError:  # wallet loading error
        await model.delete()
