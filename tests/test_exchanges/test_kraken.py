from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
import pytest_mock

from api.ext.exchanges.kraken import (
    KRAKEN_ASSET_PAIRS_URL,
    KRAKEN_TICKER_URL,
    Kraken,
    get_kraken_result,
    normalize_kraken_pair,
)

ONLINE_ASSET_PAIRS = {
    "XXBTZUSD": {"wsname": "XBT/USD", "status": "online"},
    "XETHZEUR": {"wsname": "ETH/EUR", "status": "online"},
    "DOTUSD": {"wsname": "DOT/USD", "status": "online"},
}

TICKER_PRICES = {
    "XXBTZUSD": {"c": ["100.1"]},
    "XETHZEUR": {"c": ["200.2"]},
    "DOTUSD": {"c": ["3.3"]},
}


def kraken_response(result: dict[str, Any]) -> dict[str, Any]:
    return {"error": [], "result": result}


def kraken_exchange() -> Kraken:
    return Kraken(None, None, [], {})  # type: ignore[arg-type]


def mock_kraken_requests(
    mocker: pytest_mock.MockerFixture, asset_pairs: dict[str, Any], ticker_prices: dict[str, Any]
) -> Mock:
    return mocker.patch(
        "api.ext.exchanges.kraken.utils.common.send_request",
        side_effect=[kraken_response(asset_pairs), kraken_response(ticker_prices)],
    )


@pytest.mark.anyio
async def test_kraken_refresh_loads_all_online_pairs(mocker: pytest_mock.MockerFixture) -> None:
    send_request = mock_kraken_requests(
        mocker,
        asset_pairs={**ONLINE_ASSET_PAIRS, "XXBTZJPY": {"wsname": "XBT/JPY", "status": "cancel_only"}},
        ticker_prices={**TICKER_PRICES, "XXBTZJPY": {"c": ["400.4"]}},
    )
    exchange = kraken_exchange()

    await exchange.refresh()

    assert exchange.quotes == {
        "BTC_USD": Decimal("100.1"),
        "ETH_EUR": Decimal("200.2"),
        "DOT_USD": Decimal("3.3"),
    }
    assert send_request.call_args_list == [
        mocker.call("GET", KRAKEN_ASSET_PAIRS_URL),
        mocker.call("GET", KRAKEN_TICKER_URL),
    ]


@pytest.mark.anyio
async def test_kraken_get_rate_adds_inverse_pairs(mocker: pytest_mock.MockerFixture) -> None:
    mock_kraken_requests(
        mocker,
        asset_pairs={"XETHZEUR": ONLINE_ASSET_PAIRS["XETHZEUR"]},
        ticker_prices={"XETHZEUR": {"c": ["2000"]}},
    )
    exchange = kraken_exchange()

    assert await exchange.get_rate("EUR_ETH") == Decimal("0.0005")


@pytest.mark.parametrize(
    "pair",
    [
        {},
        {"wsname": None},
        {"wsname": ""},
        {"wsname": "XBTUSD"},
    ],
)
def test_normalize_kraken_pair_rejects_invalid_wsname(pair: dict[str, Any]) -> None:
    assert normalize_kraken_pair(pair) is None


def test_normalize_kraken_pair_skips_synthetic_markets() -> None:
    assert normalize_kraken_pair({"wsname": "XBT/USD:BTNL"}) is None


def test_get_kraken_result_raises_on_error() -> None:
    response = {"error": ["EAPI:Rate limit", "EService:Unavailable"], "result": {}}

    with pytest.raises(ValueError, match="Kraken Ticker request failed: EAPI:Rate limit, EService:Unavailable"):
        get_kraken_result(response, "Ticker")


@pytest.mark.anyio
async def test_kraken_refresh_raises_on_kraken_error(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "api.ext.exchanges.kraken.utils.common.send_request",
        side_effect=[
            {"error": ["EGeneral:Invalid arguments"], "result": {}},
            kraken_response({}),
        ],
    )
    exchange = kraken_exchange()

    with pytest.raises(ValueError, match="Kraken AssetPairs request failed: EGeneral:Invalid arguments"):
        await exchange.refresh()
