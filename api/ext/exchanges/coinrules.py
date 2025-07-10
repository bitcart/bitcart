from api import utils
from api.ext.exchanges.base import BaseExchange


class BTC:
    coingecko_id = "bitcoin"


class BCH:
    coingecko_id = "bitcoin-cash"


class LTC:
    coingecko_id = "litecoin"


class XRGExchange(BaseExchange):
    async def refresh(self):
        result = await utils.common.send_request("GET", "https://explorer.ergon.network/ext/summary")
        self.quotes = {"XRG_USDT": utils.common.precise_decimal(result["data"][0]["lastPrice"])}


class XRG:
    coingecko_id = "tether"
    default_rule = "XRG_X = xrgexchange(XRG_USDT) * USDT_X"
    provides_exchange = {"name": "xrgexchange", "class": XRGExchange}


class ETH:
    coingecko_id = "ethereum"


class BNB:
    coingecko_id = "binancecoin"


class SBCH:
    default_rule = "SBCH_X = BCH_X"


class MATIC:
    coingecko_id = "matic-network"


class TRX:
    coingecko_id = "tron"


class GRS:
    coingecko_id = "groestlcoin"


class XMR:
    coingecko_id = "monero"
