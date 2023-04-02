import asyncio
import time
from abc import ABCMeta, abstractmethod
from decimal import Decimal
from typing import Dict, List

from bitcart.coin import Coin

from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


class BaseExchange(metaclass=ABCMeta):
    def __init__(self, coins: List[Coin], contracts: Dict[str, list]):
        self.coins = coins
        self.contracts = contracts
        self.quotes = {}
        self.last_refresh = 0
        self.lock = asyncio.Lock()

    async def _check_fresh(self):
        async with self.lock:
            if time.time() - self.last_refresh > 150:
                try:
                    await self.refresh()
                except Exception as e:
                    logger.error(f"Failed refreshing exchange rates:\n{get_exception_message(e)}")
                self.last_refresh = time.time()

    async def get_rate(self, pair=None):
        await self._check_fresh()
        if pair is None:
            return self.quotes
        return self.quotes.get(pair, Decimal("NaN"))

    async def get_fiat_currencies(self):
        await self._check_fresh()
        return list(map(lambda x: x.split("_")[1], self.quotes))

    @abstractmethod
    async def refresh(self):
        pass
