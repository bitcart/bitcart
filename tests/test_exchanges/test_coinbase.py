from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_mock

from api.ext.exchanges.base import REQUEST_TIMEOUT
from api.ext.exchanges.coinbase import COINBASE_PRODUCTS_URL, Coinbase, build_coinbase_quotes


def product(base: str, quote: str, price: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "product_id": f"{base}-{quote}",
        "base_currency_id": base,
        "quote_currency_id": quote,
        "price": price,
        "status": "online",
        "trading_disabled": False,
        "is_disabled": False,
        **kwargs,
    }


PRODUCTS = [
    product("BTC", "USD", "100.1"),
    product("ETH", "EUR", "200.2"),
    product("OLD", "USD", "1", status="delisted"),
    product("HALT", "USD", "1", trading_disabled=True),
    product("OFF", "USD", "1", is_disabled=True),
    product("NEW", "USD", ""),
    product("ZERO", "USD", "0"),
]


def coinbase_exchange() -> Coinbase:
    return Coinbase("coinbase", None, Mock(save_exchange_state=AsyncMock()), [], {})  # type: ignore[arg-type]


def test_build_coinbase_quotes_skips_unusable_products() -> None:
    assert build_coinbase_quotes(PRODUCTS) == {"BTC_USD": Decimal("100.1"), "ETH_EUR": Decimal("200.2")}


@pytest.mark.anyio
async def test_coinbase_fetch_quotes(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mocker.patch("api.ext.exchanges.coinbase.utils.common.send_request", return_value={"products": PRODUCTS})
    exchange = coinbase_exchange()

    assert await exchange.fetch_quotes() == {"BTC_USD": Decimal("100.1"), "ETH_EUR": Decimal("200.2")}
    send_request.assert_called_once_with("GET", COINBASE_PRODUCTS_URL, timeout=REQUEST_TIMEOUT)


@pytest.mark.anyio
async def test_coinbase_get_rate_adds_inverse_pairs(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "api.ext.exchanges.coinbase.utils.common.send_request",
        return_value={"products": [product("ETH", "EUR", "2000")]},
    )
    exchange = coinbase_exchange()

    assert await exchange.get_rate("EUR_ETH") == Decimal("0.0005")
