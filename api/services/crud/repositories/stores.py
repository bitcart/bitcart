from sqlalchemy import update
from sqlalchemy.orm import selectinload

from api import models
from api.services.crud.repository import CRUDRepository


class StoreRepository(CRUDRepository[models.Store]):
    model_type = models.Store

    LOAD_OPTIONS = [selectinload(models.Store.wallets), selectinload(models.Store.notifications)]

    async def set_wallet_order(self, store_id: str, wallet_ids: list[str]) -> None:
        if not wallet_ids:
            return
        await self.session.execute(
            update(models.WalletxStore),
            [
                {"store_id": store_id, "wallet_id": wallet_id, "position": position}
                for position, wallet_id in enumerate(wallet_ids)
            ],
        )
