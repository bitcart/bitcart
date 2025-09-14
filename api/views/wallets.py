import math
from typing import Any

from bitcart.errors import BaseError as BitcartBaseError
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, HTTPException, Security

from api import models, utils
from api.constants import AuthScopes
from api.schemas.base import DecimalAsFloat
from api.schemas.misc import BalanceResponse, CloseChannelScheme, LNPayScheme, OpenChannelScheme
from api.schemas.wallets import CreateWallet, CreateWalletData, DisplayWallet, UpdateWallet
from api.services.crud.wallets import WalletService
from api.services.wallet_data import WalletDataService
from api.types import Money
from api.utils.routing import create_crud_router

router = APIRouter(route_class=DishkaRoute)


@router.get("/balance", response_model=Money)
async def get_balances(
    wallet_service: FromDishka[WalletService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    return await wallet_service.get_wallet_balances(user)


@router.get("/schema")
async def get_wallets_schema(wallet_service: FromDishka[WalletService]) -> Any:
    return wallet_service.get_wallets_schema()


@router.post("/create")
async def create_wallet(
    wallet_service: FromDishka[WalletService],
    data: CreateWalletData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    return await wallet_service.create_wallet_seed(data)


create_crud_router(
    CreateWallet,
    UpdateWallet,
    DisplayWallet,
    WalletService,
    router=router,
    required_scopes=[AuthScopes.WALLET_MANAGEMENT],
)


@router.get("/{model_id}/rate", response_model=DecimalAsFloat)
async def get_wallet_rate(
    wallet_service: FromDishka[WalletService],
    wallet_data_service: FromDishka[WalletDataService],
    model_id: str,
    currency: str = "USD",
) -> Any:
    wallet = await wallet_service.get(model_id)
    rate = await wallet_data_service.get_rate(wallet, currency.upper(), extra_fallback=False)
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


@router.get("/{model_id}/balance", response_model=BalanceResponse)
async def get_wallet_balance(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    return await wallet_service.get_wallet_balance(model_id, user)


@router.get("/{model_id}/symbol")
async def get_wallet_symbol(
    wallet_service: FromDishka[WalletService],
    wallet_data_service: FromDishka[WalletDataService],
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    wallet = await wallet_service.get(model_id, user)
    return await wallet_data_service.get_wallet_symbol(wallet)


@router.get("/{model_id}/checkln")
async def check_wallet_lightning(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    try:
        coin = await wallet_service.get_wallet_coin_by_id(model_id, user)
        return await coin.node_id
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        return False


@router.get("/{model_id}/channels")
async def get_wallet_channels(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    try:
        coin = await wallet_service.get_wallet_coin_by_id(model_id, user)
        return await coin.list_channels()
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        return []


@router.post("/{model_id}/channels/open")
async def open_wallet_channel(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    params: OpenChannelScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    try:
        coin = await wallet_service.get_wallet_coin_by_id(model_id, user)
        return await coin.open_channel(params.node_id, params.amount)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to open channel") from None


@router.post("/{model_id}/channels/close")
async def close_wallet_channel(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    params: CloseChannelScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    try:
        coin = await wallet_service.get_wallet_coin_by_id(model_id, user)
        return await coin.close_channel(params.channel_point, force=params.force)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to close channel") from None


@router.post("/{model_id}/lnpay")
async def wallet_lnpay(
    wallet_service: FromDishka[WalletService],
    model_id: str,
    params: LNPayScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.WALLET_MANAGEMENT]),
) -> Any:
    try:
        coin = await wallet_service.get_wallet_coin_by_id(model_id, user)
        return await coin.lnpay(params.invoice)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to pay the invoice") from None
