import secrets
from typing import List

from fastapi import APIRouter, HTTPException
from nejma.ext.starlette import WebSocketEndpoint
from nejma.layers import Channel
from starlette.status import WS_1008_POLICY_VIOLATION

from . import crud, models, schemes, settings, tasks, utils

router = APIRouter()

utils.model_view(
    router,
    "/users",
    models.User,
    schemes.User,
    custom_methods={"post": crud.create_user},
)
utils.model_view(
    router,
    "/wallets",
    models.Wallet,
    schemes.Wallet,
    schemes.CreateWallet,
    background_tasks_mapping={"post": tasks.sync_wallet},
)
utils.model_view(router, "/stores", models.Store, schemes.Store, schemes.CreateStore)
utils.model_view(
    router, "/products", models.Product, schemes.Product, schemes.CreateProduct
)
utils.model_view(
    router,
    "/invoices",
    models.Invoice,
    schemes.Invoice,
    schemes.CreateInvoice,
    custom_methods={
        "get": crud.get_invoices,
        "get_one": crud.get_invoice,
        "post": crud.create_invoice,
    },
)


@router.get("/rate")
async def rate():
    return await settings.btc.rate()


@router.get("/wallet_history/{wallet}", response_model=List[schemes.TxResponse])
async def wallet_history(wallet: int):
    response: List[schemes.TxResponse] = []
    if wallet == 0:
        for model in await models.Wallet.query.gino.all():
            await utils.get_wallet_history(model, response)
    else:
        model = await models.Wallet.get(wallet)
        if not model:
            raise HTTPException(404, f"Wallet with id {wallet} does not exist!")
        await utils.get_wallet_history(model, response)
    return response


@router.post("/token")
async def create_token(input_token: schemes.CreateToken):
    user = await utils.authenticate_user(input_token.username, input_token.password)
    if not user:
        raise HTTPException(400, "Unauthorized")
    token = await models.Token.create(user)
    return {"token": token.key}


@router.websocket_route("/ws/wallets/{wallet}")
class WalletNotify(WebSocketEndpoint):
    channel_layer = settings.layer

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.wallet_id = int(websocket.path_params["wallet"])
        except ValueError:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.wallet = await models.Wallet.get(self.wallet_id)
        if not self.wallet:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        await self.channel_layer.add(str(self.wallet_id), self.channel_name)
        self.channel_layer.send = websocket.send_json

    async def on_disconnect(self, websocket, close_code):
        await self.channel_layer.remove_channel(self.channel_name)


@router.websocket_route("/ws/invoices/{invoice}")
class InvoiceNotify(WebSocketEndpoint):
    channel_layer = settings.layer

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.invoice_id = int(websocket.path_params["invoice"])
        except ValueError:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.invoice = await models.Invoice.get(self.invoice_id)
        if not self.invoice:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        await self.channel_layer.add(str(self.invoice_id), self.channel_name)
        self.channel_layer.send = websocket.send_json

    async def on_disconnect(self, websocket, close_code):
        await self.channel_layer.remove_channel(self.channel_name)
