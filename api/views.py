# pylint: disable=no-member, no-name-in-module
import json
import secrets
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic.error_wrappers import ValidationError
from sqlalchemy import distinct
from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.status import WS_1008_POLICY_VIOLATION

from . import crud, db, models, pagination, schemes, settings, tasks, utils

router = APIRouter()


def get_user():
    return models.User


def get_wallet():
    return models.User.join(models.Wallet)


def get_store():
    return models.Store.join(models.WalletxStore).join(models.Wallet).join(models.User)


def get_product():
    return (
        models.Product.join(models.Store)
        .join(models.WalletxStore)
        .join(models.Wallet)
        .join(models.User)
    )


def get_discount():
    return models.Discount.join(models.User)


def get_invoice():
    return (
        models.Invoice.join(models.Store)
        .join(models.WalletxStore)
        .join(models.Wallet)
        .join(models.User)
    )


@router.get("/users/me", response_model=schemes.DisplayUser)
async def get_me(user: models.User = Depends(utils.AuthDependency())):
    return user


@router.get("/wallets/balance", response_model=Decimal)
async def get_balances(user: models.User = Depends(utils.AuthDependency())):
    balances = Decimal()
    async with db.db.acquire() as conn:
        async with conn.transaction():
            async for wallet in models.Wallet.query.select_from(get_wallet()).where(
                models.User.id == user.id
            ).gino.iterate():
                balance = (
                    await settings.get_coin(wallet.currency, wallet.xpub).balance()
                )["confirmed"]
                balances += Decimal(balance)
    return balances


@router.get("/stores/{store}/ping")
async def ping_email(store: int, user: models.User = Depends(utils.AuthDependency())):
    model = (
        await models.Store.query.select_from(get_store())
        .where(models.Store.id == store)
        .gino.first()
    )
    if not model:
        raise HTTPException(404, f"Store with id {store} does not exist!")
    return utils.check_ping(
        model.email_host,
        model.email_port,
        model.email_user,
        model.email_password,
        model.email,
        model.email_use_ssl,
    )


# invoices and products should have unauthorized access
async def get_product_noauth(model_id: int):
    item = await models.Product.get(model_id)
    if not item:
        raise HTTPException(
            status_code=404, detail=f"Object with id {model_id} does not exist!"
        )
    await crud.product_add_related(item)
    return item


async def get_invoice_noauth(model_id: int):
    item = await models.Invoice.get(model_id)
    if not item:
        raise HTTPException(
            status_code=404, detail=f"Object with id {model_id} does not exist!"
        )
    await crud.invoice_add_related(item)
    return item


async def get_products(
    pagination: pagination.Pagination = Depends(),
    store: Optional[int] = None,
    category: Optional[str] = "",
    max_price: Optional[Decimal] = None,
    user: schemes.User = Depends(utils.AuthDependency()),
):
    return await pagination.paginate(
        models.Product,
        get_product(),
        user.id,
        store,
        category,
        max_price,
        postprocess=crud.products_add_related,
    )


async def create_product(
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Depends(utils.AuthDependency()),
):
    filename = utils.get_image_filename(image)
    data = json.loads(data)
    try:
        data = schemes.CreateProduct(**data)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    data.image = filename
    d = data.dict()
    discounts = d.pop("discounts", None)
    try:
        obj = await models.Product.create(**d)
        created = []
        for i in discounts:
            created.append(
                (
                    await models.DiscountxProduct.create(
                        product_id=obj.id, discount_id=i
                    )
                ).discount_id
            )
        obj.discounts = created
        if image:
            filename = utils.get_image_filename(image, False, obj)
            await obj.update(image=filename).apply()
            await utils.save_image(filename, image)
    except (
        asyncpg.exceptions.UniqueViolationError,
        asyncpg.exceptions.NotNullViolationError,
        asyncpg.exceptions.ForeignKeyViolationError,
    ) as e:
        raise HTTPException(422, e.message)
    return obj


async def process_edit_product(model_id, data, image, user, patch=True):
    data = json.loads(data)
    try:
        model = schemes.Product(**data)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    item = await get_product_noauth(model_id)
    if image:
        filename = utils.get_image_filename(image, False, item)
        model.image = filename
        await utils.save_image(filename, image)
    else:
        utils.safe_remove(item.image)
        model.image = None
    try:
        if patch:
            await item.update(
                **model.dict(exclude_unset=True)  # type: ignore
            ).apply()
        else:
            await item.update(**model.dict()).apply()
    except (  # pragma: no cover
        asyncpg.exceptions.UniqueViolationError,
        asyncpg.exceptions.NotNullViolationError,
        asyncpg.exceptions.ForeignKeyViolationError,
    ) as e:
        raise HTTPException(422, e.message)  # pragma: no cover
    return item


async def patch_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Depends(utils.AuthDependency()),
):
    return await process_edit_product(model_id, data, image, user)


async def put_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Depends(utils.AuthDependency()),
):
    return await process_edit_product(model_id, data, image, user, patch=False)


async def delete_product(item: schemes.Product, user: schemes.User) -> schemes.Product:
    await crud.product_add_related(item)
    utils.safe_remove(item.image)
    await item.delete()
    return item


async def products_count(
    request: Request,
    store: Optional[int] = None,
    category: Optional[str] = "",
    max_price: Optional[Decimal] = None,
):
    query = models.Product.query
    if store is None:
        user = await utils.AuthDependency()(request)
        query = query.select_from(get_product()).where(models.User.id == user.id)
    else:
        query = query.where(models.Product.store_id == store)
    if category and category != "all":
        query = query.where(models.Product.category == category)
    if max_price is not None:
        query = query.where(models.Product.amount <= max_price)
    return await (
        query.with_only_columns([db.db.func.count(distinct(models.Product.id))])
        .order_by(None)
        .gino.scalar()
    )


@router.get("/invoices/order_id/{order_id}", response_model=schemes.DisplayInvoice)
async def get_invoice_by_order_id(order_id: str):
    item = await models.Invoice.query.where(
        models.Invoice.order_id == order_id
    ).gino.first()
    if not item:
        raise HTTPException(
            status_code=404, detail=f"Object with order id {order_id} does not exist!"
        )
    await crud.invoice_add_related(item)
    return item


utils.model_view(
    router,
    "/users",
    models.User,
    schemes.User,
    get_user,
    schemes.CreateUser,
    display_model=schemes.DisplayUser,
    custom_methods={
        "post": crud.create_user,
        "patch": crud.patch_user,
        "put": crud.put_user,
    },
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
    router,
    "/stores",
    models.Store,
    schemes.Store,
    get_store,
    schemes.CreateStore,
    custom_methods={
        "get": crud.get_stores,
        "get_one": crud.get_store,
        "post": crud.create_store,
        "delete": crud.delete_store,
    },
)
utils.model_view(
    router,
    "/discounts",
    models.Discount,
    schemes.Discount,
    get_discount,
    schemes.CreateDiscount,
    custom_methods={"post": crud.create_discount},
)
utils.model_view(
    router,
    "/products",
    models.Product,
    schemes.Product,
    get_product,
    schemes.CreateProduct,
    custom_methods={"delete": delete_product},
    request_handlers={
        "get": get_products,
        "get_one": get_product_noauth,
        "post": create_product,
        "patch": patch_product,
        "put": put_product,
        "get_count": products_count,
    },
)
utils.model_view(
    router,
    "/invoices",
    models.Invoice,
    schemes.Invoice,
    get_invoice,
    schemes.CreateInvoice,
    schemes.DisplayInvoice,
    custom_methods={
        "get": crud.get_invoices,
        "get_one": crud.get_invoice,
        "post": crud.create_invoice,
        "delete": crud.delete_invoice,
    },
    request_handlers={"get_one": get_invoice_noauth},
)


@router.get("/rate")
async def rate(currency: str = "btc"):
    return await settings.get_coin(currency).rate()


@router.get("/categories")
async def categories(store: int):
    return {
        category
        for category, in await models.Product.select("category")
        .where(models.Product.store_id == store)
        .gino.all()
        if category
    }.union({"all"})


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
        data={"sub": user.email},
        token_type="access",
        expires_delta=access_token_expires,
    )
    refresh_token_expires = timedelta(days=settings.REFRESH_EXPIRE_DAYS)
    refresh_token = utils.create_access_token(
        data={"sub": user.email},
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
    user, status = await utils.authenticate_user(
        input_token.email, input_token.password
    )
    if not user:
        raise HTTPException(401, {"message": "Unauthorized", "status": status})
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
