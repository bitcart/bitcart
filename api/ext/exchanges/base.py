import asyncio
import time
from abc import ABCMeta, abstractmethod
from decimal import Decimal

from bitcart.coin import Coin

from api.ext.fxrate import ExchangePair
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)

REFRESH_TIME = 150
EXCHANGE_ACTIVE_TIME = 12 * 60 * 60

# Adaptive system: avoid refresh on call except for first time, then refresh in background
# If exchange wasn't used for 12 hours, stop refreshing in background


def get_inverse_dict(d):
    return {str(ExchangePair(k).inverse()): 1 / v for k, v in d.items()}


class BaseExchange(metaclass=ABCMeta):
    def __init__(self, coins: list[Coin], contracts: dict[str, list]):
        self.coins = coins
        self.contracts = contracts
        self.quotes = {}
        self.last_refresh = 0
        self.last_called = 0
        self.lock = asyncio.Lock()

    async def _check_fresh(self, called=False):
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

    async def get_rate(self, pair=None):
        await self._check_fresh(True)
        if pair is None:
            return self.quotes
        return self.quotes.get(pair, Decimal("NaN"))

    async def get_fiat_currencies(self):
        await self._check_fresh(True)
        return [x.split("_")[1] for x in self.quotes]

    @abstractmethod
    async def refresh(self):
        pass

    async def refresh_task(self):
        while True:
            if time.time() - self.last_called <= EXCHANGE_ACTIVE_TIME:
                await self._check_fresh()
            await asyncio.sleep(REFRESH_TIME + 1)

    async def start(self):
        asyncio.create_task(self.refresh_task())
