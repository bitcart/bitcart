from sqlalchemy.orm import selectinload

from api import models
from api.services.crud import CRUDRepository


class WalletRepository(CRUDRepository[models.Wallet]):
    model_type = models.Wallet

    LOAD_OPTIONS = [selectinload(models.Wallet.user), selectinload(models.Wallet.stores)]
