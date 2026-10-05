import asyncio
import inspect
import time
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock
from aiohttp import ClientResponseError, RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from api.ext.exchanges.base import REFRESH_TIME, STALE_TIME, BaseExchange
from api.types import Quotes

pytestmark = pytest.mark.anyio

QUOTES = {"BTC_USD": Decimal("50000")}
NEW_QUOTES = {"BTC_USD": Decimal("60000")}


class FakeExchange(BaseExchange):
    def __init__(self, *results: Any, name: str = "fake") -> None:
        self.save = AsyncMock()
        super().__init__(name, None, Mock(save_exchange_state=self.save), [], {})  # type: ignore[arg-type]
        self.fetch = AsyncMock(side_effect=results)

    async def fetch_quotes(self) -> Quotes:
        result = await self.fetch()
        return await result if inspect.isawaitable(result) else result


def stale_exchange(*results: Any) -> FakeExchange:
    exchange = FakeExchange(*results)
    exchange.set_quotes(QUOTES, time.time() - STALE_TIME - 1)
    exchange.last_attempt = exchange.fetched_at
    return exchange


def is_missing(rate: Decimal | Quotes) -> bool:
    return isinstance(rate, Decimal) and rate.is_nan()


async def slow_quotes(event: asyncio.Event) -> Quotes:
    await event.wait()
    return NEW_QUOTES


async def test_first_lookup_waits_for_refresh() -> None:
    exchange = FakeExchange(QUOTES)
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert await exchange.get_rate("USD_BTC") == Decimal("0.00002")
    assert is_missing(await exchange.get_rate("ETH_USD"))
    exchange.fetch.assert_awaited_once()
    exchange.save.assert_awaited_once_with(exchange, QUOTES)


async def test_concurrent_lookups_share_refresh() -> None:
    event = asyncio.Event()
    exchange = FakeExchange(slow_quotes(event))
    lookups = [asyncio.create_task(exchange.get_rate("BTC_USD")) for _ in range(5)]
    await asyncio.sleep(0)
    event.set()
    assert await asyncio.gather(*lookups) == [Decimal("60000")] * 5
    exchange.fetch.assert_awaited_once()


async def test_fresh_quotes_do_not_refresh_or_wait() -> None:
    event = asyncio.Event()
    exchange = FakeExchange(slow_quotes(event))
    exchange.set_quotes(QUOTES, time.time())
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    exchange.fetch.assert_not_awaited()
    exchange.refresh()
    assert await asyncio.wait_for(exchange.get_rate("BTC_USD"), 1) == Decimal("50000")
    assert exchange.is_refreshing()
    event.set()
    await exchange.refresh()


async def test_stale_quotes_refresh() -> None:
    exchange = stale_exchange(NEW_QUOTES)
    assert await exchange.get_rate("BTC_USD") == Decimal("60000")


async def test_failed_refresh_keeps_quotes_and_retries_once_per_cycle() -> None:
    exchange = stale_exchange(Exception("CoinGecko is down"), NEW_QUOTES)
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert exchange.last_error == "Exception: CoinGecko is down"
    assert exchange.last_error_at >= exchange.last_attempt
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert exchange.fetch.await_count == 1
    exchange.last_attempt -= REFRESH_TIME
    assert await exchange.get_rate("BTC_USD") == Decimal("60000")
    assert exchange.fetch.await_count == 2
    assert exchange.last_error is None
    assert exchange.get_info()["last_error_at"] is None


async def test_last_error_hides_request_headers() -> None:
    url = URL("https://pro-api.coingecko.com/api/v3/simple/price")
    headers = CIMultiDictProxy(CIMultiDict({"x-cg-pro-api-key": "secret-key"}))
    error = ClientResponseError(RequestInfo(url, "GET", headers, url), (), status=429, message="Too Many Requests")
    exchange = FakeExchange(error)
    await exchange.get_rate("BTC_USD")
    last_error = exchange.get_info()["last_error"]
    assert last_error.startswith("ClientResponseError: 429, message='Too Many Requests'")
    assert "secret-key" not in last_error


async def test_no_quotes_and_failed_refresh() -> None:
    exchange = FakeExchange(Exception("CoinGecko is down"))
    assert is_missing(await exchange.get_rate("BTC_USD"))
    assert is_missing(await exchange.get_rate("BTC_USD"))
    exchange.fetch.assert_awaited_once()
    exchange.save.assert_not_awaited()


async def test_refresh_timeout(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.REFRESH_TIMEOUT", 0.01)
    exchange = FakeExchange(slow_quotes(asyncio.Event()))
    assert is_missing(await exchange.get_rate("BTC_USD"))
    assert exchange.last_error == "TimeoutError"


async def test_invalidated_during_refresh_waits_for_next_refresh() -> None:
    event = asyncio.Event()
    exchange = stale_exchange(slow_quotes(event), {**NEW_QUOTES, "TOKEN_USD": Decimal(2)})
    first = asyncio.create_task(exchange.get_rate("BTC_USD"))
    while not exchange.fetch.await_count:
        await asyncio.sleep(0)
    exchange.invalidated = True
    lookup = asyncio.create_task(exchange.get_rate("TOKEN_USD"))
    await asyncio.sleep(0)
    event.set()
    assert await lookup == Decimal(2)
    assert exchange.fetch.await_count == 2
    assert not exchange.invalidated
    await first


async def test_invalidated_lookup_waits_one_lookup_timeout(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.LOOKUP_TIMEOUT", 0.2)
    first, second = asyncio.Event(), asyncio.Event()
    exchange = stale_exchange(slow_quotes(first), slow_quotes(second))
    exchange.refresh()
    while not exchange.fetch.await_count:
        await asyncio.sleep(0)
    exchange.invalidated = True
    lookup = asyncio.create_task(exchange.get_rate("BTC_USD"))
    await asyncio.sleep(0.1)
    first.set()
    assert await lookup == Decimal("60000")
    assert exchange.is_refreshing()
    assert asyncio.get_running_loop().time() < exchange.wait_until
    second.set()
    await exchange.refresh()


async def test_lookups_stop_waiting_once_refresh_is_slow(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.LOOKUP_TIMEOUT", 0.05)
    event = asyncio.Event()
    exchange = stale_exchange(slow_quotes(event))
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert loop.time() - started >= 0.04
    started = loop.time()
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert loop.time() - started < 0.04
    event.set()
    await exchange.refresh()
    assert await exchange.get_rate("BTC_USD") == Decimal("60000")


async def test_first_lookup_wait_is_bounded(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.LOOKUP_TIMEOUT", 0.01)
    event = asyncio.Event()
    exchange = FakeExchange(slow_quotes(event))
    assert is_missing(await exchange.get_rate("BTC_USD"))
    assert exchange.is_refreshing()
    event.set()
    await exchange.refresh()
    assert await exchange.get_rate("BTC_USD") == Decimal("60000")


async def test_invalidated_lookup_wait_is_bounded(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.LOOKUP_TIMEOUT", 0.01)
    event = asyncio.Event()
    exchange = FakeExchange(slow_quotes(event))
    exchange.set_quotes(QUOTES, time.time())
    exchange.invalidated = True
    assert await exchange.get_rate("BTC_USD") == Decimal("50000")
    assert exchange.is_refreshing()
    event.set()
    await exchange.refresh()
    assert await exchange.get_rate("BTC_USD") == Decimal("60000")


def test_refresh_delay() -> None:
    exchange = FakeExchange()
    assert exchange.get_refresh_delay() == REFRESH_TIME
    exchange.last_attempt = time.time() - 100
    assert REFRESH_TIME - 101 < exchange.get_refresh_delay() <= REFRESH_TIME - 100


async def test_hanging_save_does_not_block_refresh(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.base.SAVE_TIMEOUT", 0.01)

    async def hang(*args: Any) -> None:
        await asyncio.Event().wait()

    exchange = FakeExchange(QUOTES)
    exchange.save.side_effect = hang
    assert await asyncio.wait_for(exchange.get_rate("BTC_USD"), 1) == Decimal("50000")
    assert not exchange.is_refreshing()
