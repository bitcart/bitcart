import secrets
from datetime import timedelta
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.status import WS_1008_POLICY_VIOLATION

from . import crud, models, schemes, settings, tasks, utils

router = APIRouter()


def get_user():
    return models.User


def get_wallet():
    return models.User.join(models.Wallet)


def get_store():
    return models.Store.join(models.Wallet).join(models.User)


def get_product():
    return models.User.join(models.Wallet).join(models.Store).join(models.Product)


def get_invoice():
    return (
        models.User.join(models.Wallet)
        .join(models.Store)
        .join(models.Product)
        .join(models.ProductxInvoice)
        .join(models.Invoice)
    )


@router.get("/users/me", response_model=schemes.User)
async def get_me(user: models.User = Depends(utils.AuthDependency())):
    return user


utils.model_view(
    router,
    "/users",
    models.User,
    schemes.User,
    get_user,
    schemes.CreateUser,
    custom_methods={"post": crud.create_user},
)
utils.model_view(
    router,
    "/wallets",
    models.Wallet,
    schemes.CreateWallet,
    get_wallet,
    schemes.CreateWallet,
    schemes.Wallet,
    background_tasks_mapping={"post": tasks.sync_wallet},
    custom_methods={"post": crud.create_wallet},
)
utils.model_view(
    router, "/stores", models.Store, schemes.Store, get_store, schemes.CreateStore
)
utils.model_view(
    router,
    "/products",
    models.Product,
    schemes.Product,
    get_product,
    schemes.CreateProduct,
)
utils.model_view(
    router,
    "/invoices",
    models.Invoice,
    schemes.Invoice,
    get_invoice,
    schemes.CreateInvoice,
    custom_methods={
        "get": crud.get_invoices,
        "get_one": crud.get_invoice,
        "post": crud.create_invoice,
        "delete": crud.delete_invoice,
    },
)


@router.get("/rate")
async def rate():
    return await settings.btc.rate()


@router.get("/wallet_history/{wallet}", response_model=List[schemes.TxResponse])
async def wallet_history(
    wallet: int, user: models.User = Depends(utils.AuthDependency())
):
    response: List[schemes.TxResponse] = []
    if wallet == 0:

        for model in await models.Wallet.query.select_from(get_wallet()).gino.all():
            await utils.get_wallet_history(model, response)
    else:
        model = (
            await models.Wallet.query.select_from(get_wallet())
            .where(models.Wallet.id == wallet)
            .gino.first()
        )
        if not model:
            raise HTTPException(404, f"Wallet with id {wallet} does not exist!")
        await utils.get_wallet_history(model, response)
    return response


def create_tokens(user: models.User):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = utils.create_access_token(
        data={"sub": user.username},
        token_type="access",
        expires_delta=access_token_expires,
    )
    refresh_token_expires = timedelta(days=settings.REFRESH_EXPIRE_DAYS)
    refresh_token = utils.create_access_token(
        data={"sub": user.username},
        token_type="refresh",
        expires_delta=refresh_token_expires,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/token")
async def create_token(input_token: schemes.CreateToken):
    user = await utils.authenticate_user(input_token.username, input_token.password)
    if not user:
        raise HTTPException(401, "Unauthorized")
    return create_tokens(user)


@router.post("/refresh_token")
async def refresh_token(request: Request, refresh_token: schemes.RefreshToken):
    user = await utils.AuthDependency(token=refresh_token.token, token_type="refresh")(
        request
    )
    return create_tokens(user)


@router.websocket_route("/ws/wallets/{wallet}")
class WalletNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.wallet_id = int(websocket.path_params["wallet"])
            self.access_token = websocket.query_params["token"]
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        try:
            self.user = await utils.AuthDependency(token=self.access_token)(None)
        except HTTPException:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.wallet = (
            await models.Wallet.query.select_from(get_wallet())
            .where(models.Wallet.id == self.wallet_id)
            .gino.first()
        )
        if not self.wallet:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.subscriber, self.channel = await utils.make_subscriber(self.wallet_id)
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:{self.wallet_id}")


@router.websocket_route("/ws/invoices/{invoice}")
class InvoiceNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.invoice_id = int(websocket.path_params["invoice"])
            self.access_token = websocket.query_params["token"]
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        try:
            self.user = await utils.AuthDependency(token=self.access_token)(None)
        except HTTPException:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.invoice = (
            await models.Invoice.query.select_from(get_invoice())
            .where(models.Invoice.id == self.invoice_id)
            .gino.first()
        )
        self.invoice = await crud.get_invoice(self.invoice_id, self.invoice, self.user)
        if not self.invoice:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.subscriber, self.channel = await utils.make_subscriber(self.invoice_id)
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:{self.invoice_id}")
