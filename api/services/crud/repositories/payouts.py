from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api import models
from api.constants import PayoutStatus
from api.services.crud.repository import CRUDRepository


class PayoutRepository(CRUDRepository[models.Payout]):
    model_type = models.Payout

    LOAD_OPTIONS = [selectinload(models.Payout.wallet), selectinload(models.Payout.store), selectinload(models.Payout.user)]

    async def get_sent_payouts(self, currency: str) -> tuple[tuple[models.Payout, models.Wallet]]:
        return cast(
            tuple[tuple[models.Payout, models.Wallet]],
            (
                await self.session.execute(
                    select(models.Payout, models.Wallet)
                    .where(models.Payout.status == PayoutStatus.SENT)
                    .where(models.Wallet.id == models.Payout.wallet_id)
                    .where(models.Wallet.currency == currency)
                )
            ).all(),
        )
