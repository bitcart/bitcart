from api import utils
from api.ext.exchanges.base import BaseExchange


class Kraken(BaseExchange):
    async def refresh(self):
        ccys = ["EUR", "USD", "CAD", "GBP", "JPY"]
        pairs = ["XBT%s" % c for c in ccys]
        json = await utils.common.send_request("GET", "https://api.kraken.com/0/public/Ticker?pair=%s" % ",".join(pairs))
        self.quotes = {f"BTC_{k[-3:]}": utils.common.precise_decimal(str(v["c"][0])) for k, v in json["result"].items()}
