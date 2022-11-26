from api import models, settings, utils


async def get_wallet_coin_by_id(model_id: str, user):
    wallet = await utils.database.get_object(models.Wallet, model_id, user)
    return settings.settings.get_coin(
        wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
    )
