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
utils.model_view(
    router,
    "/stores",
    models.Store,
    schemes.Store,
    schemes.CreateStore)
utils.model_view(
    router,
    "/products",
    models.Product,
    schemes.Product,
    schemes.CreateProduct)
utils.model_view(
    router,
    "/invoices",
    models.Invoice,
    schemes.Invoice,
    schemes.CreateInvoice, custom_methods={
        "get": crud.get_invoices,
        "get_one": crud.get_invoice,
        "post": crud.create_invoice})
