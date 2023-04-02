from api import utils
from api.ext.exchanges.base import BaseExchange


class FiatExchange(BaseExchange):
    async def refresh(self):
        result = await utils.common.send_request(
            "GET", "https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/usd.json"
        )
        self.quotes = {f"USD_{k.upper()}": utils.common.precise_decimal(v) for k, v in result["usd"].items()}
