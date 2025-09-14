import asyncio
import time
from abc import ABCMeta, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

from bitcart import BTC  # type: ignore[attr-defined]

from api.ext.fxrate import ExchangePair
from api.logging import get_exception_message, get_logger
from api.settings import Settings

if TYPE_CHECKING:
    from api.services.exchange_rate import ExchangeRateService

logger = get_logger(__name__)

REFRESH_TIME = 150
EXCHANGE_ACTIVE_TIME = 12 * 60 * 60

# Adaptive system: avoid refresh on call except for first time, then refresh in background
# If exchange wasn't used for 12 hours, stop refreshing in background


def get_inverse_dict(d: dict[str, Decimal]) -> dict[str, Decimal]:
    return {str(ExchangePair(k).inverse()): 1 / v for k, v in d.items()}


class BaseExchange(metaclass=ABCMeta):
    def __init__(
        self,
        settings: Settings,
        exchange_rate_service: "ExchangeRateService",
        coins: list[BTC],
        contracts: dict[str, list[str]],
    ) -> None:
        self.settings = settings
        self.exchange_rate_service = exchange_rate_service
        self.coins = coins
        self.contracts = contracts
        self.quotes: dict[str, Decimal] = {}
        self.last_refresh: float = 0
        self.last_called: float = 0
        self.lock = asyncio.Lock()

    async def _check_fresh(self, called: bool = False) -> None:
        async with self.lock:
            cur_time = time.time()
            if (called and (self.last_refresh == 0 or cur_time - self.last_called > EXCHANGE_ACTIVE_TIME)) or (
                not called and cur_time - self.last_refresh > REFRESH_TIME
            ):
                try:
                    await self.refresh()
                    # we don't support quotes which have more than 1 underscore
                    self.quotes = {k: v for k, v in self.quotes.items() if k.count("_") == 1}
                    self.quotes.update(get_inverse_dict(self.quotes))
                except Exception as e:
                    logger.error(f"Failed refreshing exchange rates:\n{get_exception_message(e)}")
                self.last_refresh = cur_time
            if called:
                self.last_called = cur_time

    async def get_rate(self, pair: str | None = None) -> Decimal | dict[str, Decimal]:
        await self._check_fresh(True)
        if pair is None:
            return self.quotes
        return self.quotes.get(pair, Decimal("NaN"))

    async def get_fiat_currencies(self) -> list[str]:
        await self._check_fresh(True)
        return [x.split("_")[1] for x in self.quotes]

    @abstractmethod
    async def refresh(self) -> None:
        pass

    async def refresh_task(self) -> None:
        while True:
            if time.time() - self.last_called <= EXCHANGE_ACTIVE_TIME:
                await self._check_fresh()
            await asyncio.sleep(REFRESH_TIME + 1)

    async def start(self) -> None:
        asyncio.create_task(self.refresh_task())
