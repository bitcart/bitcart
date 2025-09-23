import asyncio
from decimal import Decimal
from typing import Any

from bitcart import (  # type: ignore[attr-defined]
    BTC,
    COINS,
)
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException

from api import models
from api.db import AsyncSession
from api.ext.moneyformat import currency_table
from api.logging import get_exception_message, get_logger
from api.schemas.tasks import SyncWalletMessage
from api.schemas.wallets import CreateWalletData
from api.services.coins import CoinService
from api.services.crud import CRUDService
from api.services.crud.repositories import WalletRepository
from api.services.wallet_data import WalletDataService
from api.types import TasksBroker

logger = get_logger(__name__)


class WalletService(CRUDService[models.Wallet]):
    repository_type = WalletRepository
    repository: WalletRepository

    def __init__(
        self,
        session: AsyncSession,
        broker: TasksBroker,
        coin_service: CoinService,
        wallet_data_service: WalletDataService,
    ) -> None:
        super().__init__(session)
        self.broker = broker
        self.coin_service = coin_service
        self.wallet_data_service = wallet_data_service

    async def finalize_create(self, data: dict[str, Any], user: models.User | None = None) -> models.Wallet:
        wallet = await super().finalize_create(data, user)
        await self.session.commit()
        await self.broker.publish("sync_wallet", SyncWalletMessage(wallet_id=wallet.id))
        return wallet

    async def _fetch_balance(self, semaphore: asyncio.BoundedSemaphore, model: models.Wallet) -> None:
        async with semaphore:
            model.balance = Decimal(0)
            success, model.divisibility, model.balance = await self.wallet_data_service.get_confirmed_wallet_balance(model)
            model.error = not success
            try:
                model.xpub_name = getattr(await self.coin_service.get_coin(model.currency), "xpub_name", "Xpub")
            except HTTPException:  # pragma: no cover
                model.xpub_name = COINS[model.currency.upper()].xpub_name if model.currency.upper() in COINS else "Xpub"

    async def batch_load(self, models: list[models.Wallet]) -> list[models.Wallet]:
        if not models:
            return models
        semaphore = asyncio.BoundedSemaphore(5)
        tasks = [self._fetch_balance(semaphore, model) for model in models]
        await asyncio.gather(*tasks, return_exceptions=True)
        await super().batch_load(models)
        return models

    async def get_wallet_balances(self, user: models.User) -> str:
        show_currency = user.settings.balance_currency
        balances = Decimal()
        rates: dict[tuple[str, str | None], Decimal] = {}
        result = await self.repository.stream_user_wallets(user.id)
        async for wallet in result:
            _, _, crypto_balance = await self.wallet_data_service.get_confirmed_wallet_balance(wallet)
            cache_key = (wallet.currency, wallet.contract)
            if cache_key in rates:  # pragma: no cover
                rate = rates[cache_key]
            else:
                rate = rates[cache_key] = await self.wallet_data_service.get_rate(wallet, show_currency)
            balances += crypto_balance * rate
        return currency_table.format_decimal(show_currency, currency_table.normalize(show_currency, balances))

    async def get_wallet_balance(self, model_id: str, user: models.User) -> dict[str, str]:
        wallet = await self.get(model_id, user)
        got = await self.wallet_data_service.get_wallet_balance(wallet)
        response = got[2]
        divisibility = got[1]
        formatted_response = {}
        for key in response:
            formatted_response[key] = currency_table.format_decimal(wallet.currency, response[key], divisibility=divisibility)
        return formatted_response

    async def create_wallet_seed(self, data: CreateWalletData) -> dict[str, Any]:
        coin = await self.coin_service.get_coin(data.currency)
        seed = await coin.server.make_seed()
        if data.hot_wallet:
            return {"seed": seed, "key": seed, "additional_data": {}}
        coin = await self.coin_service.get_coin(data.currency, {"xpub": seed, "diskless": True})
        try:
            key = await coin.server.getmpk() if not coin.is_eth_based else await coin.server.getaddress()
            additional_data = {}
            if data.currency.lower() == "xmr":
                additional_data = {"address": key}
                key = await coin.server.getpubkeys()
        finally:
            await coin.server.close_wallet()
        return {"seed": seed, "key": key, "additional_data": additional_data}

    @staticmethod
    def _prepare_output(data: list[str]) -> list[dict[str, str]]:
        return [{"key": v, "name": v.capitalize()} for v in data]

    def get_wallets_schema(self) -> dict[str, Any]:
        return {
            currency: {
                "required": self._prepare_output(getattr(coin, "required_xpub_fields", [])),
                "properties": self._prepare_output(coin.additional_xpub_fields),
                "xpub_name": getattr(coin, "xpub_name", "Xpub"),
            }
            for currency, coin in self.coin_service.cryptos.items()
        }

    async def get_wallet_coin_by_id(self, model_id: str, user: models.User) -> BTC:
        wallet = await self.get(model_id, user)
        return await self.coin_service.get_coin(
            wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
        )

    async def validate(self, data: dict[str, Any], model: models.Wallet, user: models.User | None = None) -> None:
        await super().validate(data, model, user)
        if any(key in data for key in ("xpub", "contract", "additional_xpub_data")):
            currency = data.get("currency", model.currency)
            coin = await self.coin_service.get_coin(currency)
            if "xpub" in data or "additional_xpub_data" in data:
                await self.validate_xpub(
                    coin,
                    currency,
                    data.get("xpub", model.xpub),
                    data.get("additional_xpub_data", model.additional_xpub_data),
                )
            if "contract" in data and data["contract"]:  # pragma: no cover
                tokens = await coin.server.get_tokens()
                data["contract"] = tokens.get(data["contract"], data["contract"])
                try:
                    if not await coin.server.validatecontract(data["contract"]):
                        raise HTTPException(422, "Invalid contract")
                    data["contract"] = await coin.server.normalizeaddress(data["contract"])
                except BitcartBaseError as e:
                    logger.error(f"Failed to validate contract for currency {currency}:\n{get_exception_message(e)}")
                    raise HTTPException(422, "Invalid contract") from None

    async def validate_xpub(self, coin: BTC, currency: str, xpub: str, additional_xpub_data: dict[str, Any]) -> None:
        try:
            if not await coin.validate_key(xpub, **additional_xpub_data):
                raise HTTPException(422, "Wallet key invalid")
        except BitcartBaseError as e:
            logger.error(f"Failed to validate xpub for currency {currency}:\n{get_exception_message(e)}")
            raise HTTPException(422, "Wallet key invalid") from None
