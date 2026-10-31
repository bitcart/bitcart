from api import utils
from api.ext.exchanges.base import BaseExchange
from api.logging import get_exception_message, get_logger
from api.types import Quotes

logger = get_logger(__name__)

FIAT_RATES_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
# Keyless fallback: ECB reference rates (~30 currencies), "Exchange rates by AllRatesToday" (https://allratestoday.com)
FIAT_FALLBACK_URL = "https://allratestoday.com/api/open/latest/USD"


class FiatExchange(BaseExchange):
    async def fetch_quotes(self) -> Quotes:
        try:
            result = await self.request("GET", FIAT_RATES_URL)
            rates = result["usd"]
        except Exception as e:
            logger.warning(f"Primary fiat rates source failed, using fallback:\n{get_exception_message(e)}")
            result = await self.request("GET", FIAT_FALLBACK_URL)
            rates = result["rates"]
        return {f"USD_{k.upper()}": utils.common.precise_decimal(v) for k, v in rates.items()}
