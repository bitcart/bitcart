import asyncio
import importlib
import inspect
import json
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from taskiq.exceptions import TaskiqError

from api import utils
from api.db import AsyncSessionMaker
from api.exceptions import ExchangeRatesUnavailableError
from api.ext.exchanges.base import LOOKUP_TIMEOUT, REFRESH_TIME, BaseExchange
from api.ext.exchanges.coingecko import coingecko_based_exchange, fetch_delayed
from api.logging import get_exception_message, get_logger
from api.redis import Redis
from api.schemas.tasks import RatesActionMessage
from api.services.coins import CoinService
from api.services.crud.repositories import WalletRepository
from api.settings import Settings
from api.types import Quotes, TasksBroker

logger = get_logger(__name__)

# Make sure to update it if the file is moved
EXCHANGES_PATH = Path(os.path.dirname(__file__)).parent / "ext" / "exchanges"
STATE_KEY_PREFIX = "exchange_rates"
CALL_TIMEOUT = LOOKUP_TIMEOUT + 10


def worker_result(func: Callable[..., Any]) -> Callable[..., Any]:
    async def wrapper(self: "ExchangeRateService", *args: Any, **kwargs: Any) -> Any:
        if self.settings.IS_WORKER or self.settings.is_testing():
            return await func(self, *args, **kwargs)
        try:
            task = await self.broker.publish("rates_action", RatesActionMessage(func=func.__name__, args=args))
            task_result = await task.wait_result(check_interval=0.01, timeout=CALL_TIMEOUT)
        except TaskiqError as e:
            raise ExchangeRatesUnavailableError("The worker did not answer the exchange rates request") from e
        task_result.raise_for_error()
        return json.loads(task_result.return_value, object_hook=utils.common.decimal_aware_object_hook)

    return wrapper


class ExchangeRateService:
    def __init__(
        self,
        async_sessionmaker: AsyncSessionMaker,
        settings: Settings,
        coin_service: CoinService,
        broker: TasksBroker,
        redis_pool: Redis,
    ) -> None:
        self.async_sessionmaker = async_sessionmaker
        self.settings = settings
        self.coin_service = coin_service
        self.broker = broker
        self.redis_pool = redis_pool
        self.load_exchanges()

    def load_exchanges(self) -> None:
        self.exchanges: dict[str, BaseExchange] = {}
        self._exchange_classes = {}
        self.contracts: dict[str, list[str]] = {}
        for filename in os.listdir(EXCHANGES_PATH):
            if filename.endswith(".py") and filename not in ("__init__.py", "base.py", "rates_manager.py", "coinrules.py"):
                module_name = os.path.splitext(filename)[0]
                module = importlib.import_module(f"api.ext.exchanges.{module_name}")
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    try:
                        if issubclass(obj, BaseExchange):
                            self._exchange_classes[module_name.lower()] = obj
                    except TypeError:
                        pass
        self.default_rules = ""
        self.coingecko_ids = {}
        coin_rules = importlib.import_module("api.ext.exchanges.coinrules")
        for currency, coin in self.coin_service.cryptos.items():
            if hasattr(coin_rules, currency.upper()):
                rules_obj = getattr(coin_rules, currency.upper())
                if hasattr(rules_obj, "default_rule"):
                    self.default_rules += rules_obj.default_rule + "\n"
                if hasattr(rules_obj, "coingecko_id"):
                    self.coingecko_ids[currency] = rules_obj.coingecko_id
                if hasattr(rules_obj, "provides_exchange"):
                    result = rules_obj.provides_exchange
                    self._exchange_classes[result["name"]] = result["class"]
            if hasattr(coin, "rate_rules"):
                self.default_rules += coin.rate_rules + "\n"

    async def init(self) -> None:
        self.lock = asyncio.Lock()
        self.coins = list(self.coin_service.cryptos.values())
        async with self.async_sessionmaker() as session:
            wallet_repository = WalletRepository(session)
            contracts = await wallet_repository.get_wallet_contracts()
        final_contracts: dict[str, list[str]] = {}
        for tokens, currency in contracts:
            if currency not in self.coin_service.cryptos:
                continue
            final_contracts[currency] = list(filter(None, tokens))
        for currency in self.coin_service.cryptos:
            if currency not in final_contracts:
                final_contracts[currency] = []
        self.contracts = final_contracts
        if self.settings.is_testing():
            self.exchanges["coingecko"] = self._exchange_classes["coingecko"](
                "coingecko", self.settings, self, self.coins, final_contracts
            )
            return
        for name, exchange_cls in self._exchange_classes.items():
            self.exchanges[name] = exchange_cls(name, self.settings, self, self.coins, final_contracts)

    async def start(self) -> None:
        await self.init()
        await self.start_exchanges(list(self.exchanges.values()))
        self.proxied_exchanges_task = utils.tasks.create_task(self.load_proxied_exchanges())

    async def start_exchanges(self, exchanges: list[BaseExchange]) -> None:
        await self.load_exchange_states(exchanges)
        for exchange in exchanges:
            await exchange.start()

    async def load_proxied_exchanges(self) -> None:
        while True:
            try:
                response = cast(
                    list[dict[str, Any]],
                    await fetch_delayed(
                        "GET", f"{self.settings.coingecko_api_url}/exchanges/list", headers=self.settings.coingecko_headers
                    ),
                )
                exchanges = [
                    coingecko_based_exchange(item["id"])(item["id"], self.settings, self, self.coins, self.contracts)
                    for item in response
                    if item["id"] not in self.exchanges
                ]
                break
            except Exception as e:
                logger.error(f"Error while fetching coingecko exchanges:\n{get_exception_message(e)}")
                await asyncio.sleep(REFRESH_TIME)
        self.exchanges.update({exchange.name: exchange for exchange in exchanges})
        await self.start_exchanges(exchanges)

    @staticmethod
    def get_state_key(name: str) -> str:
        return f"{STATE_KEY_PREFIX}:{name}"

    async def load_exchange_states(self, exchanges: list[BaseExchange]) -> None:
        if not exchanges:
            return
        states = await self.redis_pool.mget([self.get_state_key(exchange.name) for exchange in exchanges])
        for exchange, state in zip(exchanges, states, strict=True):
            if state is None:
                continue
            try:
                exchange.load_state(json.loads(state))
            except Exception as e:
                logger.error(f"Failed loading saved {exchange.name} exchange rates:\n{get_exception_message(e)}")

    async def save_exchange_state(self, exchange: BaseExchange, quotes: Quotes) -> None:
        await self.redis_pool.set(self.get_state_key(exchange.name), json.dumps(exchange.dump_state(quotes)))

    @worker_result
    async def get_rate(self, exchange: str, pair: str | None = None) -> Decimal | Quotes:
        if exchange.lower() not in self.exchanges:
            if pair is None:
                return {}
            return Decimal("NaN")
        return await self.exchanges[exchange.lower()].get_rate(pair)

    @worker_result
    async def get_fiatlist(self) -> list[str]:
        return await self.exchanges["coingecko"].get_fiat_currencies()

    @worker_result
    async def get_ratesinfo(self) -> list[dict[str, Any]]:
        return [exchange.get_info() for exchange in self.exchanges.values() if exchange.is_active()]

    async def preload_contract(self, contract: str, currency: str) -> None:
        await self.add_contract(contract, currency)
        for exchange in self.get_contract_exchanges():
            await exchange.get_quotes()

    def get_contract_exchanges(self) -> list[BaseExchange]:
        return [exchange for exchange in self.exchanges.values() if exchange.uses_contracts]

    @worker_result
    async def add_contract(self, contract: str, currency: str) -> None:
        async with self.lock:
            if contract not in self.contracts[currency]:
                self.contracts[currency].append(contract)
                for exchange in self.get_contract_exchanges():
                    exchange.invalidated = True
