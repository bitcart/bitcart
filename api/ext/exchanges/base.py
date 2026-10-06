import asyncio
import contextlib
import time
from abc import ABCMeta, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from aiohttp import ClientTimeout
from bitcart import BTC  # type: ignore[attr-defined]

from api import utils
from api.ext.fxrate import ExchangePair
from api.logging import get_exception_message, get_exception_summary, get_logger, log_errors
from api.settings import Settings
from api.types import Quotes

if TYPE_CHECKING:
    from api.services.exchange_rate import ExchangeRateService

logger = get_logger(__name__)

REFRESH_TIME = 150
EXCHANGE_ACTIVE_TIME = 12 * 60 * 60
STALE_TIME = 2 * REFRESH_TIME
LOOKUP_TIMEOUT = 10
REFRESH_TIMEOUT = 120
SAVE_TIMEOUT = 5
REQUEST_TIMEOUT = ClientTimeout(total=15)

# Adaptive system: refresh on call only when quotes are missing or stale, otherwise refresh in background
# If exchange wasn't used for 12 hours, stop refreshing in background


def get_inverse_dict(d: Quotes) -> Quotes:
    return {str(ExchangePair(k).inverse()): 1 / v for k, v in d.items() if v != 0}


class BaseExchange(metaclass=ABCMeta):
    uses_contracts = False

    def __init__(
        self,
        name: str,
        settings: Settings,
        exchange_rate_service: "ExchangeRateService",
        coins: list[BTC],
        contracts: dict[str, list[str]],
    ) -> None:
        self.name = name
        self.settings = settings
        self.exchange_rate_service = exchange_rate_service
        self.coins = coins
        self.contracts = contracts
        self.quotes: Quotes = {}
        self.fetched_at: float = 0
        self.last_attempt: float = 0
        self.last_called: float = 0
        self.last_error: str | None = None
        self.last_error_at: float = 0
        self.invalidated = False
        self.wait_until: float = 0
        self.refresh_task: asyncio.Task[None] | None = None
        self.loop_task: asyncio.Task[None] | None = None

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await utils.common.send_request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)

    def is_refreshing(self) -> bool:
        return self.refresh_task is not None and not self.refresh_task.done()

    def is_active(self) -> bool:
        return time.time() - self.last_called <= EXCHANGE_ACTIVE_TIME

    def refresh(self) -> asyncio.Task[None]:
        if self.refresh_task is None or self.refresh_task.done():
            self.wait_until = asyncio.get_running_loop().time() + LOOKUP_TIMEOUT
            self.refresh_task = utils.tasks.create_task(self._refresh())
        return self.refresh_task

    async def _refresh(self) -> None:
        self.last_attempt = time.time()
        self.invalidated = False
        try:
            quotes = await asyncio.wait_for(self.fetch_quotes(), REFRESH_TIMEOUT)
        except Exception as e:
            self.last_error = get_exception_summary(e)
            self.last_error_at = time.time()
            logger.error(f"Failed refreshing {self.name} exchange rates:\n{get_exception_message(e)}")
            return
        # we don't support quotes which have more than 1 underscore
        quotes = {k: v for k, v in quotes.items() if k.count("_") == 1}
        self.set_quotes(quotes, time.time())
        self.last_error = None
        self.last_error_at = 0
        with log_errors(logger):
            async with asyncio.timeout(SAVE_TIMEOUT):
                await self.exchange_rate_service.save_exchange_state(self, quotes)

    def set_quotes(self, quotes: Quotes, fetched_at: float) -> None:
        self.quotes = {**quotes, **get_inverse_dict(quotes)}
        self.fetched_at = fetched_at

    def dump_state(self, quotes: Quotes) -> dict[str, Any]:
        return {
            "quotes": {k: str(v) for k, v in quotes.items()},
            "fetched_at": self.fetched_at,
            "last_called": self.last_called,
        }

    def load_state(self, state: dict[str, Any]) -> None:
        self.set_quotes({k: Decimal(v) for k, v in state["quotes"].items()}, state["fetched_at"])
        self.last_called = state["last_called"]

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fetched_at": self.fetched_at or None,
            "age": round(time.time() - self.fetched_at) if self.fetched_at else None,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at or None,
        }

    async def get_quotes(self) -> Quotes:
        cur_time = time.time()
        deadline = asyncio.get_running_loop().time() + LOOKUP_TIMEOUT
        self.last_called = cur_time
        is_stale = cur_time - self.fetched_at > STALE_TIME
        if is_stale and cur_time - self.last_attempt >= REFRESH_TIME:
            self.refresh()
        while self.invalidated or (is_stale and self.is_refreshing()):
            refresh = self.refresh()
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout_at(min(self.wait_until, deadline)):
                    await asyncio.shield(refresh)
            if not refresh.done():
                break
        return self.quotes

    async def get_rate(self, pair: str | None = None) -> Decimal | Quotes:
        quotes = await self.get_quotes()
        if pair is None:
            return quotes
        return quotes.get(pair, Decimal("NaN"))

    async def get_fiat_currencies(self) -> list[str]:
        return [x.split("_")[1] for x in await self.get_quotes()]

    @abstractmethod
    async def fetch_quotes(self) -> Quotes:
        pass

    async def refresh_loop(self) -> None:
        while True:
            with log_errors(logger):
                if self.is_active() and time.time() - self.last_attempt >= REFRESH_TIME:
                    await self.refresh()
            await asyncio.sleep(self.get_refresh_delay())

    def get_refresh_delay(self) -> float:
        due_in = self.last_attempt + REFRESH_TIME - time.time()
        return due_in if due_in > 0 else REFRESH_TIME

    async def start(self) -> None:
        self.loop_task = utils.tasks.create_task(self.refresh_loop())
