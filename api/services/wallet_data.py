import math
from decimal import Decimal

from bitcart import BTC  # type: ignore[attr-defined]
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException

from api import models
from api.constants import MAX_CONTRACT_DIVISIBILITY
from api.ext import fxrate
from api.ext.moneyformat import currency_table
from api.logging import get_exception_message, get_logger
from api.services.coins import CoinService
from api.services.exchange_rate import ExchangeRateService
from api.services.plugin_registry import PluginRegistry

logger = get_logger(__name__)


class WalletDataService:
    def __init__(
        self, coin_service: CoinService, exchange_rate_service: ExchangeRateService, plugin_registry: PluginRegistry
    ) -> None:
        self.coin_service = coin_service
        self.exchange_rate_service = exchange_rate_service
        self.plugin_registry = plugin_registry

    async def get_wallet_balance(self, wallet: models.Wallet) -> tuple[bool, int, dict[str, Decimal]]:
        try:
            coin = await self.coin_service.get_coin(
                wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
            )
            divisibility = await self.get_divisibility(wallet, coin)
            return True, divisibility, await coin.balance()
        except Exception as e:
            logger.error(
                f"Error getting wallet balance for wallet {wallet.id} with currency {wallet.currency}:"
                f"\n{get_exception_message(e)}"
            )
            return False, 8, {attr: Decimal(0) for attr in BTC.BALANCE_ATTRS}

    async def get_confirmed_wallet_balance(self, wallet: models.Wallet) -> tuple[bool, int, Decimal]:
        success, divisibility, balance = await self.get_wallet_balance(wallet)
        return success, divisibility, balance["confirmed"]

    async def get_rate(
        self,
        wallet: models.Wallet,
        currency: str,
        coin: BTC | None = None,
        extra_fallback: bool = True,
        *,
        store: models.Store | None = None,
    ) -> Decimal:
        try:
            coin = coin or await self.coin_service.get_coin(
                wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
            )
            symbol = await self.get_wallet_symbol(wallet, coin)
            if symbol.lower() == currency.lower():
                return Decimal(1)
            rate = Decimal(1)
            if contract := self.get_coin_contract(coin):  # pragma: no cover
                await self.exchange_rate_service.add_contract(contract, wallet.currency)
            if store:
                rules = store.checkout_settings.rate_rules or fxrate.get_default_rules()
                rate, _ = await fxrate.calculate_rules(self.exchange_rate_service, rules, symbol.upper(), currency.upper())
            else:
                rate = await self.exchange_rate_service.get_rate("coingecko", f"{symbol.upper()}_{currency.upper()}")
            if math.isnan(rate) and extra_fallback:
                rate = Decimal(1)  # no rate available, no conversion
            rate = await self.plugin_registry.apply_filters("get_rate", rate, coin, currency)
        except (BitcartBaseError, HTTPException) as e:
            logger.error(
                f"Error fetching rates of coin {wallet.currency.upper()} for currency {currency}, falling back to 1:\n"
                f"{get_exception_message(e)}"
            )
            rate = Decimal(1)
        return currency_table.normalize(currency, rate)

    async def get_divisibility(self, wallet: models.Wallet, coin: BTC) -> int:
        divisibility = currency_table.get_currency_data(wallet.currency)["divisibility"]
        if wallet.contract:  # pragma: no cover
            divisibility = min(MAX_CONTRACT_DIVISIBILITY, await coin.server.readcontract(wallet.contract, "decimals"))
        return await self.plugin_registry.apply_filters("get_divisibility", divisibility, wallet, coin)

    def get_coin_contract(self, coin: BTC) -> str | None:
        return coin.xpub.get("contract") if isinstance(coin.xpub, dict) else None

    async def get_wallet_symbol(self, wallet: models.Wallet, coin: BTC | None = None) -> str:
        coin = coin or await self.coin_service.get_coin(
            wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
        )
        data = (
            await coin.server.readcontract(contract, "symbol")
            if (contract := self.get_coin_contract(coin))
            else wallet.currency
        )
        return await self.plugin_registry.apply_filters("get_wallet_symbol", data, wallet, coin)
