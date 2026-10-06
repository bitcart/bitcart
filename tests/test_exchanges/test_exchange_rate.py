import json
import time
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock
from dishka import Scope
from fastapi import FastAPI
from taskiq.exceptions import ResultGetError, ResultIsReadyError, SendTaskError, TaskiqResultTimeoutError

from api import utils
from api.exceptions import ExchangeRatesUnavailableError
from api.ext.exchanges.base import EXCHANGE_ACTIVE_TIME, BaseExchange
from api.ext.exchanges.coingecko import CoingeckoExchange
from api.ext.exchanges.kraken import Kraken
from api.redis import Redis
from api.schemas.tasks import SyncWalletMessage
from api.services.coins import CoinService
from api.services.crud.wallets import WalletService
from api.services.exchange_rate import ExchangeRateService
from api.settings import Settings
from api.tasks import sync_wallet

pytestmark = pytest.mark.anyio

QUOTES = {"BTC_USD": Decimal("50000")}


async def test_exchange_states_persisted(app: FastAPI, mocker: pytest_mock.MockerFixture) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    redis_pool = await app.state.dishka_container.get(Redis)
    settings = await app.state.dishka_container.get(Settings)
    name = f"test_{utils.common.unique_id()}"
    keys = [exchange_rate_service.get_state_key(name), exchange_rate_service.get_state_key(f"{name}_broken")]
    exchange = CoingeckoExchange(name, settings, exchange_rate_service, [], {})
    exchange.set_quotes(QUOTES, time.time())
    exchange.last_called = 2000
    try:
        await exchange_rate_service.save_exchange_state(exchange, QUOTES)
        saved = json.loads(await redis_pool.get(keys[0]))
        await redis_pool.set(keys[1], "{}")
        restored = CoingeckoExchange(name, settings, exchange_rate_service, [], {})
        broken = CoingeckoExchange(f"{name}_broken", settings, exchange_rate_service, [], {})
        await exchange_rate_service.load_exchange_states([restored, broken])
    finally:
        await redis_pool.delete(*keys)
    assert saved == {"quotes": {"BTC_USD": "50000"}, "fetched_at": exchange.fetched_at, "last_called": 2000}
    assert restored.quotes == exchange.quotes
    assert restored.quotes["USD_BTC"] == Decimal("0.00002")
    assert (restored.fetched_at, restored.last_called) == (exchange.fetched_at, 2000)
    assert not broken.quotes
    fetch_quotes = mocker.patch.object(restored, "fetch_quotes")
    assert await restored.get_rate("BTC_USD") == Decimal("50000")
    fetch_quotes.assert_not_awaited()


async def test_preload_contract_refreshes_quotes(app: FastAPI) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    exchange = exchange_rate_service.exchanges["coingecko"]
    loaded_at = time.time() - 1
    exchange.set_quotes(QUOTES, loaded_at)
    exchange.last_attempt = loaded_at
    await exchange_rate_service.preload_contract("0xcontract", "btc")
    assert "0xcontract" in exchange_rate_service.contracts["btc"]
    assert not exchange.invalidated
    assert exchange.fetched_at > loaded_at


@pytest.mark.parametrize(
    ("contract", "balance", "preloaded"),
    [
        ("0xcontract", AsyncMock(return_value={"confirmed": 0}), True),
        ("0xcontract", AsyncMock(side_effect=Exception("daemon down")), True),
        ("", AsyncMock(return_value={"confirmed": 0}), False),
    ],
)
async def test_sync_wallet_preloads_contract(
    app: FastAPI, mocker: pytest_mock.MockerFixture, contract: str, balance: AsyncMock, preloaded: bool
) -> None:
    wallet = Mock(id="wallet", currency="eth", xpub="xpub", contract=contract, additional_xpub_data={})
    mocker.patch.object(WalletService, "get_or_none", return_value=wallet)
    mocker.patch.object(CoinService, "get_coin", return_value=Mock(balance=balance))
    preload = mocker.patch.object(ExchangeRateService, "preload_contract")
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        await sync_wallet.original_func(SyncWalletMessage(wallet_id="wallet"), dishka_container=container)  # type: ignore[call-arg]
    assert preload.await_args_list == ([mocker.call("0xcontract", "eth")] if preloaded else [])


async def test_add_contract_invalidates_contract_exchanges(app: FastAPI, mocker: pytest_mock.MockerFixture) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    settings = await app.state.dishka_container.get(Settings)
    kraken = Kraken("kraken", settings, exchange_rate_service, [], {})
    mocker.patch.dict(exchange_rate_service.exchanges, {kraken.name: kraken})
    await exchange_rate_service.add_contract("0xnew", "btc")
    assert exchange_rate_service.exchanges["coingecko"].invalidated
    assert not kraken.invalidated


async def test_ratesinfo_lists_active_sources(app: FastAPI, mocker: pytest_mock.MockerFixture) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    settings = await app.state.dishka_container.get(Settings)
    active = Kraken("active", settings, exchange_rate_service, [], {})
    active.last_called = time.time()
    unused = Kraken("unused", settings, exchange_rate_service, [], {})
    unused.set_quotes(QUOTES, time.time() - EXCHANGE_ACTIVE_TIME - 1)
    unused.last_called = unused.fetched_at
    mocker.patch.dict(exchange_rate_service.exchanges, {active.name: active, unused.name: unused}, clear=True)
    assert [info["name"] for info in await exchange_rate_service.get_ratesinfo()] == ["active"]


@pytest.mark.parametrize(
    ("publish_error", "wait_error"),
    [
        (SendTaskError(), None),
        (None, TaskiqResultTimeoutError(timeout=1)),
        (None, ResultIsReadyError()),
        (None, ResultGetError()),
    ],
)
async def test_worker_errors_mean_rates_unavailable(
    app: FastAPI, mocker: pytest_mock.MockerFixture, publish_error: Exception | None, wait_error: Exception | None
) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    mocker.patch.object(Settings, "is_testing", return_value=False)
    task = Mock(wait_result=AsyncMock(side_effect=wait_error))
    mocker.patch.object(exchange_rate_service, "broker", Mock(publish=AsyncMock(return_value=task, side_effect=publish_error)))
    with pytest.raises(ExchangeRatesUnavailableError):
        await exchange_rate_service.get_rate("coingecko")


async def test_proxied_exchanges_load_in_background(app: FastAPI, mocker: pytest_mock.MockerFixture) -> None:
    exchange_rate_service = await app.state.dishka_container.get(ExchangeRateService)
    coingecko = exchange_rate_service.exchanges["coingecko"]
    mocker.patch.dict(exchange_rate_service.exchanges)
    mocker.patch("api.services.exchange_rate.REFRESH_TIME", 0.01)
    fetch_delayed = mocker.patch(
        "api.services.exchange_rate.fetch_delayed",
        side_effect=[Exception("CoinGecko is down"), [{"id": "binance"}, {"id": "coingecko"}]],
    )
    start = mocker.patch.object(BaseExchange, "start")
    await exchange_rate_service.load_proxied_exchanges()
    assert fetch_delayed.call_count == 2
    assert exchange_rate_service.exchanges["coingecko"] is coingecko
    assert exchange_rate_service.exchanges["binance"].name == "binance"
    start.assert_awaited_once()
