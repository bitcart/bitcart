import asyncio
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientResponse
from bitcart import BTC  # type: ignore[attr-defined]

from api import utils
from api.ext.exchanges.base import REQUEST_TIMEOUT, BaseExchange
from api.settings import Settings
from api.types import Quotes

if TYPE_CHECKING:
    from api.services.exchange_rate import ExchangeRateService


async def fetch_delayed(
    *args: Any, delay: int = 1, return_json: bool = True, **kwargs: Any
) -> tuple[ClientResponse, Any] | Any:
    resp, data = await utils.common.send_request(*args, return_json=False, timeout=REQUEST_TIMEOUT, **kwargs)
    if resp.status == 429 and delay < 60:
        await asyncio.sleep(delay)
        return await fetch_delayed(*args, **kwargs, delay=delay * 2, return_json=return_json)
    resp.raise_for_status()
    data = json.loads(data)
    if return_json:
        return data
    return resp, data


def find_by_coin(
    exchange_rate_service: "ExchangeRateService", all_coins: list[dict[str, Any]], coin: BTC
) -> dict[str, Any] | None:
    coingecko_id = exchange_rate_service.coingecko_ids.get(coin.coin_name.lower())
    if coingecko_id:
        for currency in all_coins:
            if currency.get("id", "").lower() == coingecko_id.lower():
                return currency
    for currency in all_coins:
        if currency.get("name", "").lower() == coin.friendly_name.lower():
            return currency
    for currency in all_coins:
        if currency.get("symbol", "").lower() == coin.coin_name.lower():
            return currency
    return None


def find_by_contract(all_coins: list[dict[str, Any]], contract: str) -> dict[str, Any] | None:
    for currency in all_coins:
        if contract.lower() in (x.lower() for x in currency.get("platforms", {}).values()):
            return currency
    return None


class CoingeckoExchange(BaseExchange):
    uses_contracts = True

    def __init__(
        self,
        name: str,
        settings: Settings,
        exchange_rate_service: "ExchangeRateService",
        coins: list[BTC],
        contracts: dict[str, list[str]],
    ) -> None:
        super().__init__(name, settings, exchange_rate_service, coins, contracts)
        self.coins_cache: list[dict[str, Any]] = []

    async def get_ids(self) -> dict[str, str]:
        if not self.coins_cache:
            self.coins_cache = cast(
                list[dict[str, Any]],
                await fetch_delayed(
                    "GET",
                    f"{self.settings.coingecko_api_url}/coins/list?include_platform=true",
                    headers=self.settings.coingecko_headers,
                ),
            )
        currencies = [find_by_coin(self.exchange_rate_service, self.coins_cache, coin) for coin in self.coins.copy()]
        for contracts in self.contracts.copy().values():
            currencies.extend(find_by_contract(self.coins_cache, contract) for contract in contracts)
        return {currency["id"]: currency["symbol"] for currency in currencies if currency}

    async def fetch_quotes(self) -> Quotes:
        vs_currencies = cast(
            list[str],
            await fetch_delayed(
                "GET",
                f"{self.settings.coingecko_api_url}/simple/supported_vs_currencies",
                headers=self.settings.coingecko_headers,
            ),
        )
        ids = await self.get_ids()
        data = cast(
            dict[str, dict[str, Decimal]],
            await fetch_delayed(
                "GET",
                f"{self.settings.coingecko_api_url}/simple/price?ids={','.join(ids)}"
                f"&vs_currencies={','.join(vs_currencies)}&precision=full",
                headers=self.settings.coingecko_headers,
            ),
        )
        return {
            f"{ids[k].upper()}_{k2.upper()}": utils.common.precise_decimal(v2)
            for k, v in data.items()
            if k in ids
            for k2, v2 in v.items()
        }


def coingecko_based_exchange(name: str) -> type[BaseExchange]:
    class CoingeckoBasedExchange(BaseExchange):
        def __init__(
            self,
            name: str,
            settings: Settings,
            exchange_rate_service: "ExchangeRateService",
            coins: list[BTC],
            contracts: dict[str, list[str]],
        ) -> None:
            super().__init__(name, settings, exchange_rate_service, coins, contracts)
            self.coins_cache: list[dict[str, Any]] = []

        async def fetch_quotes(self) -> Quotes:
            if not self.coins_cache:
                self.coins_cache = cast(
                    list[dict[str, Any]],
                    await fetch_delayed(
                        "GET", f"{self.settings.coingecko_api_url}/coins/list", headers=self.settings.coingecko_headers
                    ),
                )
            coins = []
            for coin in self.coins.copy():
                currency = find_by_coin(self.exchange_rate_service, self.coins_cache, coin)
                if currency:
                    coins.append(currency["id"])
            return await self.fetch_rates(coins)

        async def fetch_rates(self, coins: list[str], page: int = 1) -> Quotes:
            base_url = f"{self.settings.coingecko_api_url}/exchanges/{name}/tickers"
            resp, data = await fetch_delayed(
                "GET",
                f"{base_url}?page={page}&coin_ids={','.join(coins)}",
                return_json=False,
                headers=self.settings.coingecko_headers,
            )
            result = {f"{x['base']}_{x['target']}": utils.common.precise_decimal(x["last"]) for x in data["tickers"]}
            total = resp.headers.get("total")
            per_page = resp.headers.get("per-page")
            if page == 1 and total and per_page:
                total = int(total)
                per_page = int(per_page)
                total_pages = total // per_page
                if total % per_page != 0:
                    total_pages += 1
                for current_page in range(2, total_pages + 1):
                    result.update(await self.fetch_rates(coins, page=current_page))
            return result

    return CoingeckoBasedExchange
