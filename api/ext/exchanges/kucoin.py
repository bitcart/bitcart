from typing import Any

from api import utils
from api.ext.exchanges.base import BaseExchange
from api.types import Quotes

KUCOIN_TICKERS_URL = "https://api.kucoin.com/api/v1/market/allTickers"
KUCOIN_SUCCESS_CODE = "200000"


def get_kucoin_tickers(response: dict[str, Any]) -> list[dict[str, Any]]:
    code = response.get("code")
    if code != KUCOIN_SUCCESS_CODE:
        raise ValueError(f"KuCoin allTickers request failed: {code} {response.get('msg', '')}".strip())
    return response["data"]["ticker"]


def build_kucoin_quotes(tickers: list[dict[str, Any]]) -> Quotes:
    quotes: Quotes = {}
    for ticker in tickers:
        symbol = ticker.get("symbol")
        last = ticker.get("last")
        if not isinstance(symbol, str) or symbol.count("-") != 1 or not last:
            continue
        price = utils.common.precise_decimal(str(last))
        if price.is_finite() and price > 0:
            quotes[symbol.replace("-", "_").upper()] = price
    return quotes


class KuCoin(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        response = await self.request("GET", KUCOIN_TICKERS_URL)
        return build_kucoin_quotes(get_kucoin_tickers(response))
