from fastapi import APIRouter

from . import crud, models, schemes, utils

router = APIRouter()

utils.model_view(
    router,
    "/users",
    models.User,
    schemes.User,
    custom_methods={
        "post": crud.create_user})
utils.model_view(
    router,
    "/wallets",
    models.Wallet,
    schemes.Wallet,
    schemes.CreateWallet)
