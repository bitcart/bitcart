import json

from api import utils
from api.ext.exchanges.base import BaseExchange
from api.logging import get_exception_summary
from api.types import Quotes

# The currency-api README asks clients to fall back to the Cloudflare mirror when jsDelivr fails.
# The last URL serves the same JSON for the ECB fiat currencies (rates by allratestoday.com).
FIAT_RATES_URLS = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
    "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
    "https://allratestoday.com/api/compat/currency-api/latest/v1/currencies/usd.json",
)


class FiatExchange(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        errors = []
        for url in FIAT_RATES_URLS:
            try:
                resp, data = await self.request("GET", url, return_json=False)
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                rates = json.loads(data)["usd"]
            except Exception as e:
                errors.append(f"{url}: {get_exception_summary(e)}")
                continue
            return {f"USD_{k.upper()}": utils.common.precise_decimal(v) for k, v in rates.items()}
        raise ValueError(f"All fiat rate sources failed: {'; '.join(errors)}")
