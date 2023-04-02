import math
from decimal import Decimal
from typing import Union

from bitcart import BTC
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException

from api import models, settings, utils
from api.constants import MAX_CONTRACT_DIVISIBILITY
from api.ext import fxrate
from api.ext.moneyformat import currency_table
from api.logger import get_exception_message, get_logger
from api.plugins import apply_filters

logger = get_logger(__name__)


async def get_rate(wallet, currency, coin=None, extra_fallback=True, *, store=None):
    try:
        coin = coin or await settings.settings.get_coin(
            wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
        )
        symbol = await get_wallet_symbol(wallet, coin)
        if symbol.lower() == currency.lower():
            return Decimal(1)
        if store:
            if wallet.contract:  # pragma: no cover
                await settings.settings.exchange_rates.add_contract(wallet.contract, wallet.currency)
            rules = store.checkout_settings.rate_rules or fxrate.get_default_rules()
            rate, _ = await fxrate.calculate_rules(rules, symbol.upper(), currency.upper())
        else:
            rate = await settings.settings.exchange_rates.get_rate("coingecko", f"{symbol.upper()}_{currency.upper()}")
        if math.isnan(rate) and extra_fallback:
            rate = Decimal(1)  # no rate available, no conversion
        rate = await apply_filters("get_rate", rate, coin, currency)
    except (BitcartBaseError, HTTPException) as e:
        logger.error(
            f"Error fetching rates of coin {wallet.currency.upper()} for currency {currency}, falling back to 1:\n"
            f"{get_exception_message(e)}"
        )
        rate = Decimal(1)
    return currency_table.normalize(currency, rate)


async def get_wallet_history(model, response):
    coin = await settings.settings.get_coin(
        model.currency, {"xpub": model.xpub, "contract": model.contract, **model.additional_xpub_data}
    )
    txes = (await coin.history())["transactions"]
    for i in txes:
        response.append({"date": i["date"], "txid": i["txid"], "amount": i["bc_value"]})


async def get_wallet_balance(wallet) -> Union[bool, Decimal]:
    try:
        coin = await settings.settings.get_coin(
            wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
        )
        divisibility = await get_divisibility(wallet, coin)
        return True, divisibility, await coin.balance()
    except Exception as e:
        logger.error(
            f"Error getting wallet balance for wallet {wallet.id} with currency {wallet.currency}:\n{get_exception_message(e)}"
        )
        return False, 8, {attr: Decimal(0) for attr in BTC.BALANCE_ATTRS}


async def get_confirmed_wallet_balance(wallet) -> Union[bool, Decimal]:
    success, divisibility, balance = await get_wallet_balance(wallet)
    return success, divisibility, balance["confirmed"]


async def get_wallet_balances(user):
    show_currency = user.settings.balance_currency
    balances = Decimal()
    rates = {}
    async with utils.database.iterate_helper():
        async for wallet in models.Wallet.query.where(models.Wallet.user_id == user.id).gino.iterate():
            _, _, crypto_balance = await get_confirmed_wallet_balance(wallet)
            cache_key = (wallet.currency, wallet.contract)
            if cache_key in rates:  # pragma: no cover
                rate = rates[cache_key]
            else:
                rate = rates[cache_key] = await get_rate(wallet, show_currency)
            balances += crypto_balance * rate
    return currency_table.format_decimal(show_currency, currency_table.normalize(show_currency, balances))


async def get_divisibility(wallet, coin):
    divisibility = currency_table.get_currency_data(wallet.currency)["divisibility"]
    if wallet.contract:  # pragma: no cover
        divisibility = min(MAX_CONTRACT_DIVISIBILITY, await coin.server.readcontract(wallet.contract, "decimals"))
    return await apply_filters("get_divisibility", divisibility, wallet, coin)


async def get_wallet_symbol(wallet, coin=None):
    coin = coin or await settings.settings.get_coin(
        wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
    )
    data = await coin.server.readcontract(wallet.contract, "symbol") if wallet.contract else wallet.currency
    return await apply_filters("get_wallet_symbol", data, wallet, coin)
