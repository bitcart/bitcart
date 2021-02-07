from . import invoices, models, settings, utils
from .events import event_handler
from .logger import get_logger

logger = get_logger(__name__)


@event_handler.on("expired_task")
async def create_expired_task(event, event_data):
    invoice = await models.Invoice.get(event_data["id"])
    if not invoice:
        return
    await invoices.make_expired_task(invoice)


@event_handler.on("sync_wallet")
async def sync_wallet(event, event_data):
    model = await models.Wallet.get(event_data["id"])
    if not model:
        return
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    logger.info(f"Wallet {model.id} synced, balance: {balance['confirmed']}")
    await utils.publish_message(
        f"wallet:{model.id}", {"status": "success", "balance": str(balance["confirmed"])}
    )  # convert for json serialization
