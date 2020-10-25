from typing import Union

from . import models, settings, utils
from .logger import get_logger

logger = get_logger(__name__)


async def sync_wallet(model: Union[int, models.Wallet]):
    model = await models.Wallet.get(model)
    if not model:
        return
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    logger.info(f"Wallet {model.id} synced, balance: {balance['confirmed']}")
    await utils.publish_message(
        model.id, {"status": "success", "balance": str(balance["confirmed"])}
    )  # convert for json serialization
