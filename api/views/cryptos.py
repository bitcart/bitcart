import math
import re
from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, HTTPException

from api import constants
from api.logging import get_logger
from api.schemas.base import DecimalAsFloat
from api.services.coins import CoinService
from api.services.exchange_rate import ExchangeRateService
from api.services.plugin_registry import PluginRegistry
from api.utils.common import prepare_compliant_response

logger = get_logger(__name__)

router = APIRouter(route_class=DishkaRoute)


@router.get("")  # Note: we use empty string there as it's included as subrouter, to avoid redirects
async def get_cryptos(coin_service: FromDishka[CoinService], plugin_registry: FromDishka[PluginRegistry]) -> Any:
    return prepare_compliant_response(await plugin_registry.apply_filters("get_currencies", coin_service.get_coin_list()))


@router.get("/supported")
async def get_supported_cryptos() -> Any:
    return constants.SUPPORTED_CRYPTOS


@router.get("/rate", response_model=DecimalAsFloat)
async def rate(
    coin_service: FromDishka[CoinService],
    exchange_rate_service: FromDishka[ExchangeRateService],
    plugin_registry: FromDishka[PluginRegistry],
    currency: str = "btc",
    fiat_currency: str = "USD",
) -> Any:
    coin = await coin_service.get_coin(currency)
    rate = await plugin_registry.apply_filters(
        "get_rate",
        await exchange_rate_service.get_rate("coingecko", f"{currency.upper()}_{fiat_currency.upper()}"),
        coin,
        fiat_currency.upper(),
        None,
    )
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


@router.get("/fiatlist")
async def get_fiatlist(
    exchange_rate_service: FromDishka[ExchangeRateService],
    plugin_registry: FromDishka[PluginRegistry],
    query: str | None = None,
) -> Any:
    s: set[str] | list[str] = set(await exchange_rate_service.get_fiatlist())
    s = await plugin_registry.apply_filters("get_fiatlist", s)
    if query is not None:
        pattern = re.compile(query, re.IGNORECASE)
        s = [x for x in s if pattern.match(x)]
    return sorted(s)


@router.get("/tokens/{currency}")
async def get_tokens(coin_service: FromDishka[CoinService], plugin_registry: FromDishka[PluginRegistry], currency: str) -> Any:
    tokens = await plugin_registry.apply_filters(
        "get_tokens", await (await coin_service.get_coin(currency)).server.get_tokens(), currency
    )
    return prepare_compliant_response(list(tokens.keys()))


@router.get("/tokens/{currency}/abi")
async def get_tokens_abi(
    coin_service: FromDishka[CoinService], plugin_registry: FromDishka[PluginRegistry], currency: str
) -> Any:
    return await plugin_registry.apply_filters(
        "get_tokens_abi", await (await coin_service.get_coin(currency)).server.getabi(), currency
    )


@router.get("/explorer/{currency}")
async def get_default_explorer(
    coin_service: FromDishka[CoinService], plugin_registry: FromDishka[PluginRegistry], currency: str
) -> Any:
    return await plugin_registry.apply_filters(
        "get_default_explorer", await coin_service.get_default_explorer(currency), currency
    )


@router.get("/rpc/{currency}")
async def get_default_rpc(
    coin_service: FromDishka[CoinService], plugin_registry: FromDishka[PluginRegistry], currency: str
) -> Any:
    return await plugin_registry.apply_filters("get_default_rpc", coin_service.get_default_rpc(currency), currency)
