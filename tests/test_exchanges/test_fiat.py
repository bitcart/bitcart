from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock
from aiohttp import ClientConnectionError

from api.ext.exchanges.base import REQUEST_TIMEOUT
from api.ext.exchanges.fiat import FIAT_FALLBACK_URL, FIAT_RATES_URL, FiatExchange

pytestmark = pytest.mark.anyio


def fiat_exchange() -> FiatExchange:
    return FiatExchange("fiat", None, Mock(save_exchange_state=AsyncMock()), [], {})  # type: ignore[arg-type]


async def test_fiat_fetch_quotes_uses_primary_source(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mocker.patch(
        "api.ext.exchanges.fiat.utils.common.send_request",
        return_value={"date": "2026-10-30", "usd": {"eur": 0.86, "btc": 0.0000091}},
    )
    assert await fiat_exchange().fetch_quotes() == {"USD_EUR": Decimal("0.86"), "USD_BTC": Decimal("0.0000091")}
    assert send_request.call_args_list == [mocker.call("GET", FIAT_RATES_URL, timeout=REQUEST_TIMEOUT)]


async def test_fiat_fetch_quotes_falls_back_when_primary_fails(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mocker.patch(
        "api.ext.exchanges.fiat.utils.common.send_request",
        side_effect=[ClientConnectionError(), {"result": "success", "base_code": "USD", "rates": {"USD": 1, "EUR": 0.86}}],
    )
    assert await fiat_exchange().fetch_quotes() == {"USD_USD": Decimal(1), "USD_EUR": Decimal("0.86")}
    assert send_request.call_args_list == [
        mocker.call("GET", FIAT_RATES_URL, timeout=REQUEST_TIMEOUT),
        mocker.call("GET", FIAT_FALLBACK_URL, timeout=REQUEST_TIMEOUT),
    ]


async def test_fiat_fetch_quotes_raises_when_both_sources_fail(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "api.ext.exchanges.fiat.utils.common.send_request",
        side_effect=[ClientConnectionError(), ClientConnectionError()],
    )
    with pytest.raises(ClientConnectionError):
        await fiat_exchange().fetch_quotes()
