import math
from typing import List

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, HTTPException, Security

from api import crud, models, schemes, settings, utils
from api.ext.moneyformat import currency_table
from api.types import Money

router = APIRouter()


@router.get("/history/all", response_model=List[schemes.TxResponse])
async def all_wallet_history(
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    response: List[schemes.TxResponse] = []
    for model in await models.Wallet.query.where(models.Wallet.user_id == user.id).gino.all():
        await utils.wallets.get_wallet_history(model, response)
    return response


@router.get("/history/{model_id}", response_model=List[schemes.TxResponse])
async def wallet_history(
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    response: List[schemes.TxResponse] = []
    model = await utils.database.get_object(models.Wallet, model_id, user)
    await utils.wallets.get_wallet_history(model, response)
    return response


@router.get("/balance", response_model=Money)
async def get_balances(user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"])):
    return await utils.wallets.get_wallet_balances(user)


@router.get("/{model_id}/balance", response_model=schemes.BalanceResponse)
async def get_wallet_balance(
    model_id: str, user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"])
):
    wallet = await utils.database.get_object(models.Wallet, model_id, user)
    got = await utils.wallets.get_wallet_balance(wallet)
    response = got[2]
    divisibility = got[1]
    for key in response:
        response[key] = currency_table.format_decimal(wallet.currency, response[key], divisibility=divisibility)
    return response


@router.get("/{model_id}/checkln")
async def check_wallet_lightning(
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    try:
        coin = await crud.wallets.get_wallet_coin_by_id(model_id, user)
        return await coin.node_id
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        return False


@router.get("/{model_id}/channels")
async def get_wallet_channels(
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    try:
        coin = await crud.wallets.get_wallet_coin_by_id(model_id, user)
        return await coin.list_channels()
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        return []


@router.post("/{model_id}/channels/open")
async def open_wallet_channel(
    model_id: str,
    params: schemes.OpenChannelScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    try:
        coin = await crud.wallets.get_wallet_coin_by_id(model_id, user)
        return await coin.open_channel(params.node_id, params.amount)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to open channel")


@router.post("/{model_id}/channels/close")
async def close_wallet_channel(
    model_id: str,
    params: schemes.CloseChannelScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    try:
        coin = await crud.wallets.get_wallet_coin_by_id(model_id, user)
        return await coin.close_channel(params.channel_point, force=params.force)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to close channel")


@router.post("/{model_id}/lnpay")
async def wallet_lnpay(
    model_id: str,
    params: schemes.LNPayScheme,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    try:
        coin = await crud.wallets.get_wallet_coin_by_id(model_id, user)
        return await coin.lnpay(params.invoice)
    except (BitcartBaseError, HTTPException) as e:
        if isinstance(e, HTTPException) and e.status_code != 422:
            raise
        raise HTTPException(400, "Failed to pay the invoice")


@router.get("/schema")
async def get_wallets_schema():
    return {
        currency: {
            "required": getattr(coin, "required_xpub_fields", []),
            "properties": coin.additional_xpub_fields,
            "xpub_name": getattr(coin, "xpub_name", "Xpub"),
        }
        for currency, coin in settings.settings.cryptos.items()
    }


@router.post("/create")
async def create_wallet(
    data: schemes.CreateWalletData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["wallet_management"]),
):
    coin = await settings.settings.get_coin(data.currency)
    seed = await coin.server.make_seed()
    if data.hot_wallet:
        return {"seed": seed, "key": seed, "additional_data": {}}
    else:
        coin = await settings.settings.get_coin(data.currency, {"xpub": seed, "diskless": True})
        try:
            key = await coin.server.getmpk() if not coin.is_eth_based else await coin.server.getaddress()
            additional_data = {}
            if data.currency.lower() == "xmr":  # pragma: no cover
                additional_data = {"address": key}
                key = await coin.server.getpubkeys()
        finally:
            await coin.server.close_wallet()
        return {"seed": seed, "key": key, "additional_data": additional_data}


@router.get("/{model_id}/rate")
async def get_wallet_rate(
    model_id: str,
    currency: str = "USD",
):
    wallet = await utils.database.get_object(models.Wallet, model_id)
    rate = await utils.wallets.get_rate(wallet, currency.upper(), extra_fallback=False)
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


utils.routing.ModelView.register(
    router,
    "/",
    models.Wallet,
    schemes.CreateWallet,
    schemes.CreateWallet,
    schemes.Wallet,
    background_tasks_mapping={"post": "sync_wallet"},
    scopes=["wallet_management"],
)
