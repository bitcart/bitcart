from api import models
from api.services.crud import CRUDRepository


class WalletRepository(CRUDRepository[models.Wallet]):
    model_type = models.Wallet
