from typing import Any

from api import utils
from api.ext.exchanges.base import BaseExchange
from api.types import Quotes

COINBASE_PRODUCTS_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"
COINBASE_ONLINE_STATUS = "online"


def build_coinbase_quotes(products: list[dict[str, Any]]) -> Quotes:
    quotes: Quotes = {}
    for product in products:
        if product.get("status") != COINBASE_ONLINE_STATUS or product.get("trading_disabled") or product.get("is_disabled"):
            continue
        base = product.get("base_currency_id")
        quote = product.get("quote_currency_id")
        price = product.get("price")
        if not base or not quote or not price:
            continue
        value = utils.common.precise_decimal(str(price))
        if value.is_finite() and value > 0:
            quotes[f"{base}_{quote}".upper()] = value
    return quotes


class Coinbase(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        response = await self.request("GET", COINBASE_PRODUCTS_URL)
        return build_coinbase_quotes(response["products"])
