from typing import cast

from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncScalarResult
from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class WalletRepository(CRUDRepository[models.Wallet]):
    model_type = models.Wallet

    LOAD_OPTIONS = [selectinload(models.Wallet.user), selectinload(models.Wallet.stores)]

    async def get_wallet_contracts(self) -> tuple[tuple[list[str | None], str]]:
        return cast(
            tuple[tuple[list[str | None], str]],
            (
                (
                    await self.session.execute(
                        select(func.array_agg(distinct(models.Wallet.contract)), models.Wallet.currency).group_by(
                            models.Wallet.currency
                        )
                    )
                ).all()
            ),
        )

    async def get_ordered_wallets(self, wallets_ids: list[str]) -> tuple[models.Wallet]:
        wallet_order = func.unnest(array(wallets_ids)).table_valued("id", with_ordinality="ord").render_derived("t")
        query = select(models.Wallet).join(wallet_order, wallet_order.c.id == models.Wallet.id).order_by(wallet_order.c.ord)
        wallets_result = await self.session.execute(query)
        return cast(tuple[models.Wallet], wallets_result.scalars().all())

    async def stream_user_wallets(self, user_id: str) -> AsyncScalarResult[models.Wallet]:
        return await self.session.stream_scalars(select(models.Wallet).where(models.Wallet.user_id == user_id))
