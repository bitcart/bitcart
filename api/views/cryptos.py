import math
import re

from fastapi import APIRouter, HTTPException

from api import constants, settings
from api.logger import get_logger
from api.plugins import apply_filters
from api.utils.common import prepare_compliant_response

logger = get_logger(__name__)

router = APIRouter()


@router.get("")  # Note: we use empty string there as it's included as subrouter, to avoid redirects
async def get_cryptos():
    return prepare_compliant_response(await apply_filters("get_currencies", list(settings.settings.cryptos.keys())))


@router.get("/supported")
async def get_supported_cryptos():
    return constants.SUPPORTED_CRYPTOS


@router.get("/rate")
async def rate(currency: str = "btc", fiat_currency: str = "USD"):
    coin = await settings.settings.get_coin(currency)
    rate = await apply_filters(
        "get_rate",
        await settings.settings.exchange_rates.get_rate("coingecko", f"{currency.upper()}_{fiat_currency.upper()}"),
        coin,
        fiat_currency.upper(),
        None,
    )
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


@router.get("/fiatlist")
async def get_fiatlist(query: str | None = None):
    s = set(await settings.settings.exchange_rates.get_fiatlist())
    s = await apply_filters("get_fiatlist", s)
    if query is not None:
        pattern = re.compile(query, re.IGNORECASE)
        s = [x for x in s if pattern.match(x)]
    return sorted(s)


@router.get("/tokens/{currency}")
async def get_tokens(currency: str):
    tokens = await apply_filters(
        "get_tokens", await (await settings.settings.get_coin(currency)).server.get_tokens(), currency
    )
    return prepare_compliant_response(list(tokens.keys()))


@router.get("/tokens/{currency}/abi")
async def get_tokens_abi(currency: str):
    return await apply_filters("get_tokens_abi", await (await settings.settings.get_coin(currency)).server.getabi(), currency)


@router.get("/explorer/{currency}")
async def get_default_explorer(currency: str):
    return await apply_filters("get_default_explorer", await settings.settings.get_default_explorer(currency), currency)


@router.get("/rpc/{currency}")
async def get_default_rpc(currency: str):
    return await apply_filters("get_default_rpc", settings.settings.get_default_rpc(currency), currency)
