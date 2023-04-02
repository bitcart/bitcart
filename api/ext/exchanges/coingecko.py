import asyncio
import json

from api import settings, utils
from api.ext.exchanges.base import BaseExchange


async def fetch_delayed(*args, delay=1, **kwargs):
    resp, data = await utils.common.send_request(*args, return_json=False)
    if resp.status == 429:
        if delay < 60:
            await asyncio.sleep(delay)
            return await fetch_delayed(*args, **kwargs, delay=delay * 2)
        resp.raise_for_status()
    data = json.loads(data)
    if kwargs.get("return_json", True):
        return data
    return resp, data


def find_by_coin(all_coins, coin):
    coingecko_id = settings.settings.exchange_rates.coingecko_ids.get(coin.coin_name.lower())
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


def find_by_contract(all_coins, contract):
    for currency in all_coins:
        if contract in currency.get("platforms", {}).values():
            return currency


def find_id(all_coins, x):
    for coin in all_coins:
        if coin["id"] == x:
            return coin["symbol"]


class CoingeckoExchange(BaseExchange):
    def __init__(self, coins, contracts):
        super().__init__(coins, contracts)
        self.coins_cache = {}

    async def refresh(self):
        vs_currencies = await fetch_delayed("GET", "https://api.coingecko.com/api/v3/simple/supported_vs_currencies")
        if not self.coins_cache:
            self.coins_cache = await fetch_delayed("GET", "https://api.coingecko.com/api/v3/coins/list?include_platform=true")
        coins = []
        for coin in self.coins.copy():
            currency = find_by_coin(self.coins_cache, coin)
            if currency:
                coins.append(currency["id"])
        for contracts in self.contracts.copy().values():
            for contract in contracts:
                currency = find_by_contract(self.coins_cache, contract)
                if currency:
                    coins.append(currency["id"])
        data = await fetch_delayed(
            "GET",
            (
                f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coins)}"
                f"&vs_currencies={','.join(vs_currencies)}&precision=full"
            ),
        )
        self.quotes = {
            f"{find_id(self.coins_cache, k).upper()}_{k2.upper()}": utils.common.precise_decimal(v2)
            for k, v in data.items()
            for k2, v2 in v.items()
        }


def coingecko_based_exchange(name):
    class CoingeckoBasedExchange(BaseExchange):
        def __init__(self, coins, contracts):
            super().__init__(coins, contracts)
            self.coins_cache = {}

        async def refresh(self):
            if not self.coins_cache:
                self.coins_cache = await fetch_delayed("GET", "https://api.coingecko.com/api/v3/coins/list")
            coins = []
            for coin in self.coins.copy():
                currency = find_by_coin(self.coins_cache, coin)
                if currency:
                    coins.append(currency["id"])
            self.quotes = await self.fetch_rates(coins)

        async def fetch_rates(self, coins, page=1):
            base_url = f"https://api.coingecko.com/api/v3/exchanges/{name}/tickers"
            page = 1
            resp, data = await fetch_delayed("GET", f"{base_url}?page={page}&coin_ids={','.join(coins)}", return_json=False)
            result = {f"{x['base']}_{x['target']}": utils.common.precise_decimal(x["last"]) for x in data["tickers"]}
            total = resp.headers.get("total")
            per_page = resp.headers.get("per-page")
            if page == 1 and total and per_page:
                total = int(total)
                per_page = int(per_page)
                total_pages = total // per_page
                if total % per_page != 0:
                    total_pages += 1
                for page in range(2, total_pages + 1):
                    result.update(await self.fetch_rates(page=page))
            return result

    return CoingeckoBasedExchange
