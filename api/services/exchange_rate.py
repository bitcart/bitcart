import asyncio
import importlib
import inspect
import json
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from api import utils
from api.db import AsyncSessionMaker
from api.ext.exchanges.base import BaseExchange
from api.ext.exchanges.coingecko import coingecko_based_exchange
from api.logging import get_exception_message, get_logger
from api.redis import Redis
from api.schemas.tasks import RatesActionMessage
from api.services.coins import CoinService
from api.services.crud.repositories import WalletRepository
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)

# Make sure to update it if the file is moved
EXCHANGES_PATH = Path(os.path.dirname(__file__)).parent / "ext" / "exchanges"


def worker_result(func: Callable[..., Any]) -> Callable[..., Any]:
    async def wrapper(self: "ExchangeRateService", *args: Any, **kwargs: Any) -> Any:
        if self.settings.IS_WORKER or self.settings.is_testing():
            return await func(self, *args, **kwargs)
        task = await self.broker.publish("rates_action", RatesActionMessage(func=func.__name__, args=args))
        task_result = await task.wait_result(check_interval=0.01)
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
        coins = list(self.coin_service.cryptos.values())
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
            self.exchanges["coingecko"] = self._exchange_classes["coingecko"](self.settings, self, coins, final_contracts)
            return
        for name, exchange_cls in self._exchange_classes.items():
            self.exchanges[name] = exchange_cls(self.settings, self, coins, final_contracts)
        try:
            coingecko_exchanges = await utils.common.send_request(
                "GET",
                f"{self.settings.coingecko_api_url}/exchanges/list",
                headers=self.settings.coingecko_headers,
            )
            for exchange in coingecko_exchanges:
                if exchange["id"] not in self.exchanges:
                    self.exchanges[exchange["id"]] = coingecko_based_exchange(exchange["id"])(
                        self.settings, self, coins, final_contracts
                    )
        except Exception as e:
            logger.error(f"Error while fetching coingecko exchanges:\n{get_exception_message(e)}")

    async def start(self) -> None:
        await self.init()
        for exchange in self.exchanges.values():
            await exchange.start()

    @worker_result
    async def get_rate(self, exchange: str, pair: str | None = None) -> Decimal | dict[str, Decimal]:
        if exchange.lower() not in self.exchanges:
            if pair is None:
                return {}
            return Decimal("NaN")
        return await self.exchanges[exchange.lower()].get_rate(pair)

    @worker_result
    async def get_fiatlist(self) -> list[str]:
        return await self.exchanges["coingecko"].get_fiat_currencies()

    @worker_result
    async def add_contract(self, contract: str, currency: str) -> None:
        async with self.lock:
            if contract not in self.contracts[currency]:
                self.contracts[currency].append(contract)
                for key in self.exchanges.copy():
                    self.exchanges[key].last_refresh = 0
