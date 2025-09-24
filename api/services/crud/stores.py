from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from api import models
from api.db import AsyncSession
from api.ext import fxrate
from api.schemas.policies import GlobalStorePolicy
from api.schemas.stores import DisplayStore, PublicStore
from api.services.crud import CRUDService
from api.services.crud.repositories import NotificationRepository, StoreRepository, WalletRepository
from api.services.exchange_rate import ExchangeRateService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService


class StoreService(CRUDService[models.Store]):
    repository_type = StoreRepository

    def __init__(
        self,
        session: AsyncSession,
        wallet_repository: WalletRepository,
        notification_repository: NotificationRepository,
        setting_service: SettingService,
        exchange_rate_service: ExchangeRateService,
        plugin_registry: PluginRegistry,
    ) -> None:
        super().__init__(session, plugin_registry)
        self.wallet_repository = wallet_repository
        self.notification_repository = notification_repository
        self.setting_service = setting_service
        self.exchange_rate_service = exchange_rate_service

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        data = await super().prepare_data(data)
        await self._process_many_to_many_field(data, "wallets", self.wallet_repository)
        await self._process_many_to_many_field(data, "notifications", self.notification_repository)
        return data

    async def finalize_create(self, data: dict[str, Any], user: models.User | None = None) -> models.Store:
        store = await super().finalize_create(data, user)
        if user and user.is_superuser:
            count = await self.repository.count()
            # First store created by superuser is the one shown on store POS
            # Substract one because current one is already created
            if count - 1 == 0:
                await self.plugin_registry.run_hook("first_store", store)
                await self.setting_service.set_setting(GlobalStorePolicy(pos_id=store.id))
        return store

    async def get_public_store(
        self, item_id: Any, user: models.User | None = None, *args: Any, **kwargs: Any
    ) -> PublicStore | DisplayStore:
        # we pass None here to allow a different user to view a public-only version
        store = await super().get(item_id, None, *args, **kwargs)
        if user and user.id == store.user_id:
            return DisplayStore.model_validate(store)
        return PublicStore.model_validate(store)

    async def set_store_rate_rules(self, model_id: str, rules: str, user: models.User) -> str:
        model = await self.get(model_id, user)
        model.checkout_settings.rate_rules = rules
        try:
            result, resolved = await fxrate.calculate_rules(self.exchange_rate_service, rules, "BTC", "USD")
        except Exception as e:
            raise HTTPException(422, str(e)) from None
        await model.set_json_key("checkout_settings", model.checkout_settings)
        return f"BTC_USD: {result} resolved by {resolved}"

    async def get_store_rates(self, model_id: str, currencies: list[str]) -> dict[str, list[dict[str, Any]]]:
        model = await self.get(model_id)
        results = []
        for currency in currencies:
            try:
                parts = currency.split("_")
                if len(parts) != 2:
                    results.append({"rate": Decimal("NaN"), "message": f"{currency}: invalid currency pair"})
                    continue
                result, resolved = await fxrate.calculate_rules(
                    self.exchange_rate_service, model.checkout_settings.rate_rules, parts[0], parts[1]
                )
                results.append({"rate": result, "message": f"{currency}: {result} (resolved by {resolved})"})
            except Exception as e:
                results.append({"rate": Decimal("NaN"), "message": f"{currency}: {str(e)}"})
        return {"rates": results}
