from api import utils
from api.ext.exchanges.base import BaseExchange
from api.types import Quotes


class FiatExchange(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        result = await self.request(
            "GET", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        )
        return {f"USD_{k.upper()}": utils.common.precise_decimal(v) for k, v in result["usd"].items()}
