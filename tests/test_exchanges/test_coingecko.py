from decimal import Decimal
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_mock
from aiohttp import ClientResponseError
from bitcart import BTC, MATIC, XRG  # type: ignore[attr-defined]

from api.ext.exchanges.base import REQUEST_TIMEOUT, BaseExchange
from api.ext.exchanges.coingecko import CoingeckoExchange, coingecko_based_exchange
from api.services.exchange_rate import ExchangeRateService
from tests.fixtures.pytest.coingecko import FakeCoingecko

pytestmark = pytest.mark.anyio

API_URL = "https://api.coingecko.com/api/v3"


def coingecko_exchange(contracts: dict[str, list[str]] | None = None, coins: list[BTC] | None = None) -> CoingeckoExchange:
    settings = Mock(coingecko_api_url=API_URL, coingecko_headers={})
    coins = coins or [BTC()]
    coin_service = Mock(cryptos={coin.coin_name.lower(): coin for coin in coins})
    exchange_rate_service = ExchangeRateService(Mock(), Mock(), coin_service, Mock(), Mock())
    return CoingeckoExchange("coingecko", settings, exchange_rate_service, coins, contracts or {})


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


@pytest.mark.parametrize("contracts", [["0xusdc", "Tusdc"], ["Tusdc", "0xusdc"]])
async def test_coingecko_symbol_collision_prefers_top_market_cap(fake_coingecko: FakeCoingecko, contracts: list[str]) -> None:
    fake_coingecko.coins += [
        {"id": "usd-coin", "symbol": "usdc", "name": "USDC", "platforms": {"ethereum": "0xusdc"}},
        {"id": "circle-bridged-usdc-tron", "symbol": "usdc", "name": "Bridged USDC", "platforms": {"tron": "Tusdc"}},
    ]
    fake_coingecko.prices |= {"usd-coin": {"usd": 1, "eur": 0.9}, "circle-bridged-usdc-tron": {"usd": 0.85, "eur": 0.76}}
    fake_coingecko.market_caps |= {"usd-coin": 70_000_000_000, "circle-bridged-usdc-tron": 0}
    assert await coingecko_exchange({"eth": contracts}).fetch_quotes() == {
        "BTC_USD": Decimal(50000),
        "BTC_EUR": Decimal(45000),
        "USDC_USD": Decimal(1),
        "USDC_EUR": Decimal("0.9"),
    }


async def test_coingecko_matic_priced_as_pol(fake_coingecko: FakeCoingecko) -> None:
    fake_coingecko.coins += [
        {"id": "matic-network", "symbol": "matic", "name": "MATIC (migrated to POL)", "platforms": {}},
        {"id": "polygon-ecosystem-token", "symbol": "pol", "name": "POL (ex-MATIC)", "platforms": {"ethereum": "0xpol"}},
    ]
    fake_coingecko.prices |= {"matic-network": {"usd": 0.126}, "polygon-ecosystem-token": {"usd": 0.091}}
    assert await coingecko_exchange({"eth": ["0xpol"]}, [MATIC()]).fetch_quotes() == {
        "MATIC_USD": Decimal("0.091"),
        "POL_USD": Decimal("0.091"),
    }


async def test_coingecko_xrg_fetches_tether_as_usdt(fake_coingecko: FakeCoingecko) -> None:
    fake_coingecko.coins.append({"id": "tether", "symbol": "usdt", "name": "Tether", "platforms": {}})
    fake_coingecko.prices["tether"] = {"usd": 1}
    assert await coingecko_exchange(coins=[XRG()]).fetch_quotes() == {"USDT_USD": Decimal(1)}


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
