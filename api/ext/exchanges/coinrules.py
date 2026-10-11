from api import utils
from api.ext.exchanges.base import BaseExchange
from api.types import Quotes


class BTC:
    coingecko_id = "bitcoin"


class BCH:
    coingecko_id = "bitcoin-cash"


class LTC:
    coingecko_id = "litecoin"


class XRGExchange(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        result = await self.request("GET", "https://explorer.ergon.network/ext/summary")
        return {"XRG_USDT": utils.common.precise_decimal(result["data"][0]["lastPrice"])}


class XRG:
    coingecko_id = "tether"
    default_rule = "XRG_X = xrgexchange(XRG_USDT) * USDT_X"
    provides_exchange = {"name": "xrgexchange", "class": XRGExchange}


class ETH:
    coingecko_id = "ethereum"


class BNB:
    coingecko_id = "binancecoin"


class MATIC:
    coingecko_id = "polygon"


class TRX:
    coingecko_id = "tron"


class GRS:
    coingecko_id = "groestlcoin"


class XMR:
    coingecko_id = "monero"


class ARBETH:
    coingecko_id = "ethereum"
