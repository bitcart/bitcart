from typing import Union

from . import models, settings, utils


async def sync_wallet(model: Union[int, models.Wallet]):
    model = await models.Wallet.get(model)
    if not model:
        return
    coin = settings.get_coin(model.currency, model.xpub)
    balance = await coin.balance()
    await utils.publish_message(
        model.id, {"status": "success", "balance": str(balance["confirmed"])}
    )  # convert for json serialization
