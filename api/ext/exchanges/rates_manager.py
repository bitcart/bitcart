import importlib
import inspect
import os
from decimal import Decimal

from sqlalchemy import distinct, select

from api import events, models, settings, utils
from api.db import db
from api.ext.exchanges.base import BaseExchange
from api.ext.exchanges.coingecko import coingecko_based_exchange
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


def worker_result(func):
    async def wrapper(self, *args, **kwargs):
        if settings.settings.is_worker or settings.settings.functional_tests:
            return await func(self, *args, **kwargs)
        async with utils.redis.wait_for_redis():
            task_id = utils.common.unique_id()
            await events.event_handler.publish("rates_action", {"func": func.__name__, "args": args, "task_id": task_id})
            return await utils.redis.wait_for_task_result(task_id)

    return wrapper


class RatesManager:
    def __init__(self, settings_obj):
        self.exchanges = {}
        self._exchange_classes = {}
        for filename in os.listdir(os.path.dirname(__file__)):
            if filename.endswith(".py") and filename not in ("__init__.py", "base.py", "rates_manager.py", "coinrules.py"):
                module_name = os.path.splitext(filename)[0]
                module = importlib.import_module(f"api.ext.exchanges.{module_name}")
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    try:
                        if issubclass(obj, BaseExchange):
                            self._exchange_classes[module_name.lower()] = obj
                    except TypeError:
                        pass
        self.default_rules = ""
        self.coingecko_ids = {}
        coin_rules = importlib.import_module("api.ext.exchanges.coinrules")
        for currency, coin in settings_obj.cryptos.items():
            if hasattr(coin_rules, currency.upper()):
                rules_obj = getattr(coin_rules, currency.upper())
                if hasattr(rules_obj, "default_rule"):
                    self.default_rules += rules_obj.default_rule + "\n"
                if hasattr(rules_obj, "coingecko_id"):
                    self.coingecko_ids[currency] = rules_obj.coingecko_id
            if hasattr(coin, "rate_rules"):
                self.default_rules += coin.rate_rules + "\n"

    async def init(self):
        coins = list(settings.settings.cryptos.values())
        contracts = (
            await select([db.func.array_agg(distinct(models.Wallet.contract)), models.Wallet.currency])
            .group_by(models.Wallet.currency)
            .gino.all()
        )
        final_contracts = {}
        for tokens, currency in contracts:
            if currency not in settings.settings.cryptos:
                continue
            final_contracts[currency] = list(filter(None, tokens))
        if settings.settings.functional_tests:
            self.exchanges["coingecko"] = self._exchange_classes["coingecko"](coins, final_contracts)
            return
        for name, exchange_cls in self._exchange_classes.items():
            self.exchanges[name] = exchange_cls(coins, final_contracts)
        try:
            coingecko_exchanges = await utils.common.send_request("GET", "https://api.coingecko.com/api/v3/exchanges/list")
            for exchange in coingecko_exchanges:
                if exchange["id"] not in self.exchanges:
                    self.exchanges[exchange["id"]] = coingecko_based_exchange(exchange["id"])(coins, final_contracts)
        except Exception as e:
            logger.error(f"Error while fetching coingecko exchanges:\n{get_exception_message(e)}")

    @worker_result
    async def get_rate(self, exchange, pair=None):
        if exchange.lower() not in self.exchanges:
            if pair is None:
                return {}
            return Decimal("NaN")
        return await self.exchanges[exchange.lower()].get_rate(pair)

    @worker_result
    async def get_fiatlist(self):
        return await self.exchanges["coingecko"].get_fiat_currencies()

    @worker_result
    async def add_contract(self, contract, currency):
        for exchange in self.exchanges.values():
            if contract not in exchange.contracts[currency]:
                exchange.contracts[currency].append(contract)
                exchange.last_refresh = 0
