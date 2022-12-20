import math
import re
from typing import Optional

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, HTTPException

from api import constants, settings
from api.logger import get_exception_message, get_logger
from api.plugins import apply_filters
from api.utils.common import prepare_compliant_response

logger = get_logger(__name__)

router = APIRouter()


@router.get("")  # Note: we use empty string there as it's included as subrouter, to avoid redirects
async def get_cryptos():
    return prepare_compliant_response(list(settings.settings.cryptos.keys()))


@router.get("/supported")
async def get_supported_cryptos():
    return constants.SUPPORTED_CRYPTOS


@router.get("/rate")
async def rate(currency: str = "btc", fiat_currency: str = "USD"):
    coin = settings.settings.get_coin(currency)
    rate = await apply_filters("get_rate", await coin.rate(fiat_currency.upper()), coin, fiat_currency.upper(), None)
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


@router.get("/fiatlist")
async def get_fiatlist(query: Optional[str] = None):
    s = None
    for coin in settings.settings.cryptos:
        try:
            fiat_list = await settings.settings.cryptos[coin].list_fiat()
        except BitcartBaseError as e:
            logger.error(
                f"Failed fetching supported currencies for coin {settings.settings.cryptos[coin].coin_name}. Daemon not"
                f" running?\n{get_exception_message(e)}"
            )
            continue
        if not s:
            s = set(fiat_list)
        else:
            s = s.intersection(fiat_list)
    if not s:
        s = set()
    s = await apply_filters("get_fiatlist", s)
    if query is not None:
        pattern = re.compile(query, re.IGNORECASE)
        s = [x for x in s if pattern.match(x)]
    return sorted(s)


@router.get("/tokens/{currency}")
async def get_tokens(currency: str):
    tokens = await apply_filters("get_tokens", await settings.settings.get_coin(currency).server.get_tokens(), currency)
    return prepare_compliant_response(list(tokens.keys()))


@router.get("/tokens/{currency}/abi")
async def get_tokens_abi(currency: str):
    return await apply_filters("get_tokens_abi", await settings.settings.get_coin(currency).server.getabi(), currency)


@router.get("/explorer/{currency}")
async def get_default_explorer(currency: str):
    return await apply_filters("get_default_explorer", settings.settings.get_default_explorer(currency), currency)


@router.get("/rpc/{currency}")
async def get_default_rpc(currency: str):
    return await apply_filters("get_default_rpc", settings.settings.get_default_rpc(currency), currency)
