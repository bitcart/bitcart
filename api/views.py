from typing import List

from fastapi import APIRouter, HTTPException
from starlette.websockets import WebSocket

from . import crud, models, schemes, settings, tasks, utils

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
    schemes.CreateWallet,
    background_tasks_mapping={"post": tasks.sync_wallet})
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


@router.get("/rate")
async def rate():
    return await settings.btc.rate()


@router.get("/wallet_history/{wallet}",
            response_model=List[schemes.TxResponse])
async def wallet_history(wallet: int):
    response: List[schemes.TxResponse] = []
    if wallet == 0:
        for model in await models.Wallet.query.gino.all():
            await utils.get_wallet_history(model, response)
    else:
        model = await models.Wallet.get(wallet)
        if not model:
            raise HTTPException(
                404, f"Wallet with id {wallet} does not exist!")
        await utils.get_wallet_history(model, response)
    return response


@router.post("/token")
async def create_token(input_token: schemes.CreateToken):
    user = await utils.authenticate_user(input_token.username, input_token.password)
    if not user:
        raise HTTPException(400, "Unauthorized")
    token = await models.Token.create(user)
    return {"token": token.key}


@router.websocket_route("/ws/wallets")
class TestRedis(utils.RedisWebSocketEndPoint):
    async def on_receive(self, ws, data):
        await self.channel_layer.publish_to_redis(data)
        print(data)
