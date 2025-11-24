import asyncio
from collections import defaultdict
from typing import Any, cast

from dishka import AsyncContainer
from fastapi import HTTPException
from sqlalchemy import select, update

from api import models
from api.constants import PayoutStatus
from api.db import AsyncSession
from api.logging import get_exception_message, get_logger
from api.schemas.misc import BatchAction
from api.services.coins import CoinService
from api.services.crud import CRUDAction, CRUDService
from api.services.crud.repositories import PayoutRepository, StoreRepository, WalletRepository
from api.services.payout_manager import PayoutManager

logger = get_logger(__name__)


class PayoutService(CRUDService[models.Payout]):
    repository_type = PayoutRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        store_repository: StoreRepository,
        wallet_repository: WalletRepository,
        coin_service: CoinService,
        payout_manager: PayoutManager,
    ) -> None:
        super().__init__(session, container)
        self.store_repository = store_repository
        self.wallet_repository = wallet_repository
        self.coin_service = coin_service
        self.payout_manager = payout_manager

    async def prepare_create(self, data: dict[str, Any], user: models.User | None = None) -> dict[str, Any]:
        data = await super().prepare_create(data, user)
        store = await self.store_repository.get_one(id=data["store_id"])
        data["currency"] = data["currency"] or store.default_currency or "USD"
        data["user_id"] = store.user_id
        data["status"] = PayoutStatus.PENDING
        return data

    async def validate(
        self, action: CRUDAction, data: dict[str, Any], model: models.Payout, user: models.User | None = None
    ) -> None:
        await super().validate(action, data, model, user)
        if "destination" in data or "wallet_id" in data:
            wallet_currency = cast(
                str,
                await self.wallet_repository.get(
                    data.get("wallet_id", model.wallet_id), statement=select(models.Wallet.currency), load=[]
                ),
            )
            coin = await self.coin_service.get_coin(wallet_currency)
            destination = data.get("destination", model.destination)
            if not await coin.server.validateaddress(destination):
                raise HTTPException(422, "Invalid destination address")
            data["destination"] = await coin.server.normalizeaddress(destination)

    @property
    def supported_batch_actions(self) -> list[str]:
        return super().supported_batch_actions + ["approve", "send", "cancel"]

    async def process_batch_action(self, settings: BatchAction, user: models.User, **kwargs: Any) -> bool:
        if settings.command == "approve":
            await self.update_many(
                update(models.Payout)
                .values({"status": PayoutStatus.APPROVED})
                .where(models.Payout.status == PayoutStatus.PENDING),
                settings.ids,
                user,
            )
            return True
        if settings.command == "cancel":
            await self.update_many(
                update(models.Payout).values({"status": PayoutStatus.CANCELLED}),
                settings.ids,
                user,
            )
            return True
        if settings.command == "send":
            await self.send_payouts(settings, user)
            return True
        return await super().process_batch_action(settings, user, **kwargs)

    async def send_payouts(self, settings: BatchAction, user: models.User) -> None:
        wallets = cast(dict[str, Any], settings.options).get("wallets", {})
        if cast(dict[str, Any], settings.options).get("batch", False):
            payouts, _ = await self.list_and_count(id=models.Payout.id.in_(settings.ids), user=user)
            wallet_to_payout = defaultdict(list)
            for cur_payout in payouts:
                wallet_to_payout[cur_payout.wallet_id].append(cur_payout)
            for wallet_id, payouts in wallet_to_payout.items():
                try:
                    await self.payout_manager.send_batch_payouts(payouts, private_key=wallets.get(wallet_id))
                except Exception as e:
                    logger.error(get_exception_message(e))
                    coros = []
                    for cur_payout in payouts:
                        coros.append(self.payout_manager.update_status(cur_payout, PayoutStatus.FAILED))
                    await asyncio.gather(*coros)
        else:
            for payout_id in settings.ids:
                payout = await self.get_or_none(payout_id, user)
                if not payout:
                    continue
                try:
                    await self.payout_manager.send_payout(payout, private_key=wallets.get(payout.wallet_id))
                except Exception as e:
                    logger.error(get_exception_message(e))
                    await self.payout_manager.update_status(payout, PayoutStatus.FAILED)
