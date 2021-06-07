import math
from decimal import Decimal

from api import models, settings, utils
from api.ext.moneyformat import currency_table


async def get_rate(coin, currency, fallback_currency=None):
    rate = await coin.rate(currency)
    if math.isnan(rate) and fallback_currency:
        rate = await coin.rate(fallback_currency)
    if math.isnan(rate):
        rate = await coin.rate("USD")
    if math.isnan(rate):
        rate = Decimal(1)  # no rate available, no conversion
    return rate


async def get_wallet_history(model, response):
    coin = settings.get_coin(model.currency, model.xpub)
    txes = (await coin.history())["transactions"]
    for i in txes:
        response.append({"date": i["date"], "txid": i["txid"], "amount": i["bc_value"]})


async def get_wallet_balance(coin):
    return (await coin.balance())["confirmed"]


async def get_wallet_balances(user):
    show_currency = user.settings.balance_currency
    balances = Decimal()
    rates = {}
    async with utils.database.iterate_helper():
        async for wallet in models.Wallet.query.where(models.Wallet.user_id == user.id).gino.iterate():
            coin = settings.get_coin(wallet.currency, wallet.xpub)
            crypto_balance = await get_wallet_balance(coin)
            if wallet.currency in rates:  # pragma: no cover
                rate = rates[wallet.currency]
            else:
                rate = rates[wallet.currency] = await get_rate(coin, show_currency)
            balances += crypto_balance * rate
    return currency_table.normalize(show_currency, balances)
