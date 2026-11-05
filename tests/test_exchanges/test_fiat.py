from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock

from api.ext.exchanges.base import REQUEST_TIMEOUT
from api.ext.exchanges.fiat import FIAT_RATES_URLS, FiatExchange


def fiat_exchange() -> FiatExchange:
    return FiatExchange("fiat", None, Mock(save_exchange_state=AsyncMock()), [], {})  # type: ignore[arg-type]


def response(status: int, body: str) -> tuple[Mock, str]:
    return Mock(status=status), body


def mock_fiat_requests(mocker: pytest_mock.MockerFixture, *results: Any) -> Mock:
    return mocker.patch("api.ext.exchanges.fiat.utils.common.send_request", side_effect=list(results))


@pytest.mark.anyio
async def test_fiat_fetch_quotes_uses_first_source(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mock_fiat_requests(mocker, response(200, '{"date": "2026-11-01", "usd": {"eur": 0.86, "usd": 1}}'))

    assert await fiat_exchange().fetch_quotes() == {"USD_EUR": Decimal("0.86"), "USD_USD": Decimal("1")}
    send_request.assert_called_once_with("GET", FIAT_RATES_URLS[0], return_json=False, timeout=REQUEST_TIMEOUT)


@pytest.mark.anyio
async def test_fiat_fetch_quotes_falls_back_on_errors(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mock_fiat_requests(
        mocker,
        response(503, "Service Unavailable"),
        response(200, "<html>not json</html>"),
        response(200, '{"date": "2026-10-30", "usd": {"gbp": 0.75}}'),
    )

    assert await fiat_exchange().fetch_quotes() == {"USD_GBP": Decimal("0.75")}
    assert [call.args[1] for call in send_request.call_args_list] == list(FIAT_RATES_URLS)


@pytest.mark.anyio
async def test_fiat_fetch_quotes_raises_when_all_sources_fail(mocker: pytest_mock.MockerFixture) -> None:
    mock_fiat_requests(
        mocker,
        OSError("connection reset"),
        response(200, '{"date": "2026-11-01"}'),
        response(404, '{"error": "not found"}'),
    )

    with pytest.raises(ValueError, match="All fiat rate sources failed") as exc_info:
        await fiat_exchange().fetch_quotes()
    assert "HTTP 404" in str(exc_info.value)
    assert "KeyError" in str(exc_info.value)
