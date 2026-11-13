from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock

from api.ext.exchanges.base import REQUEST_TIMEOUT
from api.ext.exchanges.kucoin import KUCOIN_TICKERS_URL, KuCoin, build_kucoin_quotes, get_kucoin_tickers

TICKERS = [
    {"symbol": "BTC-USDT", "last": "100.1"},
    {"symbol": "eth-btc", "last": "0.05"},
    {"symbol": "NEW-USDT", "last": None},
    {"symbol": "DEAD-USDT", "last": "0"},
    {"symbol": "ODD-X-USDT", "last": "1"},
    {"last": "1"},
]


def kucoin_response(tickers: list[dict[str, Any]]) -> dict[str, Any]:
    return {"code": "200000", "data": {"time": 1, "ticker": tickers}}


def kucoin_exchange() -> KuCoin:
    return KuCoin("kucoin", None, Mock(save_exchange_state=AsyncMock()), [], {})  # type: ignore[arg-type]


def test_build_kucoin_quotes_skips_unusable_tickers() -> None:
    assert build_kucoin_quotes(TICKERS) == {"BTC_USDT": Decimal("100.1"), "ETH_BTC": Decimal("0.05")}


def test_get_kucoin_tickers_raises_on_error() -> None:
    with pytest.raises(ValueError, match="KuCoin allTickers request failed: 429000 Too many requests"):
        get_kucoin_tickers({"code": "429000", "msg": "Too many requests"})


@pytest.mark.anyio
async def test_kucoin_fetch_quotes(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mocker.patch("api.ext.exchanges.kucoin.utils.common.send_request", return_value=kucoin_response(TICKERS))
    exchange = kucoin_exchange()

    assert await exchange.fetch_quotes() == {"BTC_USDT": Decimal("100.1"), "ETH_BTC": Decimal("0.05")}
    send_request.assert_called_once_with("GET", KUCOIN_TICKERS_URL, timeout=REQUEST_TIMEOUT)


@pytest.mark.anyio
async def test_kucoin_get_rate_adds_inverse_pairs(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "api.ext.exchanges.kucoin.utils.common.send_request",
        return_value=kucoin_response([{"symbol": "ETH-EUR", "last": "2000"}]),
    )
    exchange = kucoin_exchange()

    assert await exchange.get_rate("EUR_ETH") == Decimal("0.0005")


@pytest.mark.anyio
async def test_kucoin_fetch_quotes_raises_on_kucoin_error(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.ext.exchanges.kucoin.utils.common.send_request", return_value={"code": "400100", "msg": "Bad"})
    exchange = kucoin_exchange()

    with pytest.raises(ValueError, match="KuCoin allTickers request failed: 400100 Bad"):
        await exchange.fetch_quotes()
