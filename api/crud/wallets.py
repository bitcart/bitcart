from typing import Iterable

from api import models, pagination, schemes, settings, utils


async def create_wallet(wallet: schemes.CreateWallet, user: schemes.User):
    wallet = await models.Wallet.create(**wallet.dict(), user_id=user.id)
    await wallet_add_related(wallet)
    return wallet


async def wallet_add_related(item: models.Wallet):
    if not item:
        return
    item.balance = await utils.wallets.get_wallet_balance(settings.get_coin(item.currency, item.xpub))


async def wallets_add_related(items: Iterable[models.Wallet]):
    for item in items:
        await wallet_add_related(item)
    return items


async def get_wallet(model_id: int, user: schemes.User, item: models.Wallet, internal: bool = False):
    await wallet_add_related(item)
    return item


async def get_wallets(pagination: pagination.Pagination, user: schemes.User):
    return await pagination.paginate(models.Wallet, user.id, postprocess=wallets_add_related)


async def get_wallet_coin_by_id(model_id: int, user):
    wallet = await utils.database.get_object(models.Wallet, model_id, user)
    await wallet_add_related(wallet)
    return settings.get_coin(wallet.currency, wallet.xpub)
