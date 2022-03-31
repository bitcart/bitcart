import math
import re
from typing import Optional

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, HTTPException

from api import constants, settings
from api.logger import get_exception_message, get_logger
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
    rate = await settings.settings.get_coin(currency).rate(fiat_currency.upper())
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
    if query is not None:
        pattern = re.compile(query, re.IGNORECASE)
        s = [x for x in s if pattern.match(x)]
    return sorted(s)


@router.get("/tokens/{currency}")
async def get_tokens(currency: str):
    tokens = await settings.settings.get_coin(currency).server.get_tokens()
    return prepare_compliant_response(list(tokens.keys()))
