from decimal import Decimal
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_mock
from aiohttp import ClientResponseError
from bitcart import BTC  # type: ignore[attr-defined]

from api.ext.exchanges.base import REQUEST_TIMEOUT, BaseExchange
from api.ext.exchanges.coingecko import CoingeckoExchange, coingecko_based_exchange
from tests.fixtures.pytest.coingecko import FakeCoingecko

pytestmark = pytest.mark.anyio

API_URL = "https://api.coingecko.com/api/v3"


def coingecko_exchange() -> CoingeckoExchange:
    settings = Mock(coingecko_api_url=API_URL, coingecko_headers={})
    return CoingeckoExchange("coingecko", settings, Mock(coingecko_ids={}), [BTC()], {})


def proxied_exchange(name: str) -> BaseExchange:
    settings = Mock(coingecko_api_url=API_URL, coingecko_headers={})
    return coingecko_based_exchange(name)(name, settings, Mock(coingecko_ids={}), [BTC()], {})


async def test_coingecko_based_exchange_fetches_all_pages(fake_coingecko: FakeCoingecko) -> None:
    fake_coingecko.tickers["binance"] = [
        [{"base": "BTC", "target": "USDT", "last": 50000}, {"base": "BTC", "target": "EUR", "last": 45000}],
        [{"base": "BTC", "target": "USD", "last": 50010}],
    ]
    assert await proxied_exchange("binance").fetch_quotes() == {
        "BTC_USDT": Decimal(50000),
        "BTC_EUR": Decimal(45000),
        "BTC_USD": Decimal(50010),
    }
    assert [(url.split("?")[0], timeout) for url, timeout in fake_coingecko.requests] == [
        (f"{API_URL}/coins/list", REQUEST_TIMEOUT),
        (f"{API_URL}/exchanges/binance/tickers", REQUEST_TIMEOUT),
        (f"{API_URL}/exchanges/binance/tickers", REQUEST_TIMEOUT),
    ]
    assert [parse_qs(urlparse(url).query).get("page") for url, _ in fake_coingecko.requests] == [None, ["1"], ["2"]]


async def test_coingecko_exchange_fetches_prices() -> None:
    assert await coingecko_exchange().fetch_quotes() == {"BTC_USD": Decimal(50000), "BTC_EUR": Decimal(45000)}


async def test_coingecko_recovers_after_error_response(fake_coingecko: FakeCoingecko) -> None:
    exchange = coingecko_exchange()
    fake_coingecko.status = 401
    with pytest.raises(ClientResponseError):
        await exchange.fetch_quotes()
    assert not exchange.coins_cache
    fake_coingecko.status = 200
    assert await exchange.fetch_quotes() == {"BTC_USD": Decimal(50000), "BTC_EUR": Decimal(45000)}


async def test_coingecko_rate_limit_backoff(fake_coingecko: FakeCoingecko, mocker: pytest_mock.MockerFixture) -> None:
    sleep = mocker.patch("api.ext.exchanges.coingecko.asyncio.sleep")
    fake_coingecko.status = 429
    with pytest.raises(ClientResponseError):
        await coingecko_exchange().fetch_quotes()
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2, 4, 8, 16, 32]
