from decimal import Decimal
from typing import Any

from api import utils
from api.ext.exchanges.base import BaseExchange

KRAKEN_API_URL = "https://api.kraken.com/0/public"
KRAKEN_ASSET_PAIRS_URL = f"{KRAKEN_API_URL}/AssetPairs"
KRAKEN_TICKER_URL = f"{KRAKEN_API_URL}/Ticker"
KRAKEN_ASSET_ALIASES = {"XBT": "BTC"}
KRAKEN_ONLINE_STATUS = "online"


def normalize_kraken_asset(asset: str) -> str:
    return KRAKEN_ASSET_ALIASES.get(asset, asset).upper()


def normalize_kraken_pair(pair: dict[str, Any]) -> str | None:
    wsname = pair.get("wsname")
    if not isinstance(wsname, str) or "/" not in wsname:
        return None
    base, quote = wsname.split("/", maxsplit=1)
    return f"{normalize_kraken_asset(base)}_{normalize_kraken_asset(quote)}"


def get_kraken_result(response: dict[str, Any], endpoint: str) -> dict[str, Any]:
    errors = response.get("error") or []
    if errors:
        raise ValueError(f"Kraken {endpoint} request failed: {', '.join(errors)}")
    return response["result"]


def get_online_kraken_pairs(asset_pairs: dict[str, Any]) -> dict[str, str]:
    return {
        pair_id: normalized_pair
        for pair_id, pair in asset_pairs.items()
        if pair.get("status") == KRAKEN_ONLINE_STATUS
        if (normalized_pair := normalize_kraken_pair(pair)) is not None
    }


def build_kraken_quotes(asset_pairs: dict[str, Any], ticker: dict[str, Any]) -> dict[str, Decimal]:
    pairs = get_online_kraken_pairs(asset_pairs)
    return {
        pairs[pair_id]: utils.common.precise_decimal(str(ticker_data["c"][0]))
        for pair_id, ticker_data in ticker.items()
        if pair_id in pairs and ticker_data.get("c")
    }


class Kraken(BaseExchange):
    async def refresh(self) -> None:
        asset_pairs_response = await utils.common.send_request("GET", KRAKEN_ASSET_PAIRS_URL)
        ticker_response = await utils.common.send_request("GET", KRAKEN_TICKER_URL)
        asset_pairs = get_kraken_result(asset_pairs_response, "AssetPairs")
        ticker = get_kraken_result(ticker_response, "Ticker")
        self.quotes = build_kraken_quotes(asset_pairs, ticker)
