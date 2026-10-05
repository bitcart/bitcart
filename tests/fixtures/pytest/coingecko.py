from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_mock
from aiohttp import ClientResponseError

from api import utils
from api.constants import SUPPORTED_CRYPTOS

COINGECKO_HOSTS = ("api.coingecko.com", "pro-api.coingecko.com")


class FakeCoingecko:
    def __init__(self) -> None:
        self.status = 200
        self.vs_currencies = ["btc", "usd", "eur"]
        self.coins = [{"id": coin, "symbol": coin, "name": coin.upper(), "platforms": {}} for coin in SUPPORTED_CRYPTOS]
        self.prices: dict[str, dict[str, Any]] = {}
        self.exchanges: list[dict[str, Any]] = []
        self.tickers: dict[str, list[list[dict[str, Any]]]] = {}
        self.requests: list[tuple[str, Any]] = []

    def respond(self, url: str, timeout: Any) -> tuple[Mock, str]:
        self.requests.append((url, timeout))
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        headers: dict[str, str] = {}
        if self.status != 200:
            error = ClientResponseError(Mock(real_url=url), (), status=self.status)
            resp = Mock(status=self.status, headers=headers, raise_for_status=Mock(side_effect=error))
            return resp, json.dumps({"status": {"error_code": self.status}})
        body: Any
        if parsed.path.endswith("/coins/list"):
            body = self.coins
        elif parsed.path.endswith("/simple/supported_vs_currencies"):
            body = self.vs_currencies
        elif parsed.path.endswith("/simple/price"):
            ids = filter(None, query["ids"][0].split(","))
            body = {coin_id: self.prices.get(coin_id, {"usd": 50000, "eur": 45000}) for coin_id in ids}
        elif parsed.path.endswith("/exchanges/list"):
            body = self.exchanges
        else:
            pages = self.tickers.get(parsed.path.split("/")[-2], [[]])
            headers = {"total": str(sum(len(page) for page in pages)), "per-page": str(max(len(pages[0]), 1))}
            body = {"tickers": pages[int(query["page"][0]) - 1]}
        return Mock(status=200, headers=headers), json.dumps(body)


@pytest.fixture(autouse=True)
def fake_coingecko(mocker: pytest_mock.MockerFixture) -> FakeCoingecko:
    fake = FakeCoingecko()
    send_request = utils.common.send_request

    async def route(method: str, url: str, *args: Any, return_json: bool = True, **kwargs: Any) -> Any:
        if urlparse(url).hostname not in COINGECKO_HOSTS:
            return await send_request(method, url, *args, return_json=return_json, **kwargs)
        resp, text = fake.respond(url, kwargs.get("timeout"))
        return json.loads(text) if return_json else (resp, text)

    mocker.patch("api.utils.common.send_request", new=AsyncMock(side_effect=route))
    return fake
