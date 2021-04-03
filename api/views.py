import json
import math
import os
import re
import secrets
from decimal import Decimal
from typing import List, Optional

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, Security, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import SecurityScopes
from pydantic.error_wrappers import ValidationError
from sqlalchemy import distinct, func, select
from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.status import WS_1008_POLICY_VIOLATION

from . import constants, crud, db, models, pagination, schemes, settings, templates, utils
from .ext import configurator
from .ext import export as export_ext
from .ext import tor as tor_ext
from .ext import update as update_ext
from .invoices import InvoiceStatus

router = APIRouter()


@router.get("/users/me", response_model=schemes.DisplayUser)
async def get_me(user: models.User = Security(utils.AuthDependency())):
    return user


@router.get("/wallets/balance", response_model=Decimal)
async def get_balances(user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"])):
    balances = Decimal()
    async with db.db.acquire() as conn:
        async with conn.transaction():
            async for wallet in models.Wallet.query.where(models.Wallet.user_id == user.id).gino.iterate():
                balances += await utils.get_wallet_balance(settings.get_coin(wallet.currency, wallet.xpub))
    return balances


@router.get("/stores/{model_id}/ping")
async def ping_email(
    model_id: int,
    user: models.User = Security(utils.AuthDependency(), scopes=["store_management"]),
):
    model = await models.Store.query.where(models.Store.id == model_id).gino.first()
    if not model:
        raise HTTPException(404, f"Store with id {model_id} does not exist!")
    return utils.check_ping(
        model.email_host,
        model.email_port,
        model.email_user,
        model.email_password,
        model.email,
        model.email_use_ssl,
    )


@router.patch("/stores/{model_id}/checkout_settings", response_model=schemes.Store)
async def set_store_checkout_settings(
    model_id: int,
    settings: schemes.StoreCheckoutSettings,
    user: models.User = Security(utils.AuthDependency(), scopes=["store_management"]),
):
    model = await models.Store.get(model_id)
    if not model:
        raise HTTPException(404, f"Store with id {model_id} does not exist!")
    await model.set_setting(settings)
    await crud.store_add_related(model)
    return model


# invoices and products should have unauthorized access
async def get_product_noauth(model_id: int, store: Optional[int] = None):
    query = models.Product.query.where(models.Product.id == model_id)
    if store is not None:
        query = query.where(models.Product.store_id == store)
    item = await query.gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
    await crud.product_add_related(item)
    return item


async def get_invoice_noauth(model_id: int):
    item = await models.Invoice.get(model_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
    await crud.invoice_add_related(item)
    return item


async def get_products(
    request: Request,
    pagination: pagination.Pagination = Depends(),
    store: Optional[int] = None,
    category: Optional[str] = "",
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
):
    try:
        user = await utils.AuthDependency()(request, SecurityScopes(["product_management"]))
    except HTTPException:
        if store is None:
            raise
        user = None
    return await pagination.paginate(
        models.Product,
        user.id if user else None,
        store,
        category,
        min_price,
        max_price,
        sale,
        postprocess=crud.products_add_related,
    )


async def create_product(
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.AuthDependency(), scopes=["product_management"]),
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
    with utils.safe_db_write():
        obj = await models.Product.create(**d, user_id=user.id)
        created = []
        for i in discounts:
            created.append((await models.DiscountxProduct.create(product_id=obj.id, discount_id=i)).discount_id)
        obj.discounts = created
        if image:
            filename = utils.get_image_filename(image, False, obj)
            await obj.update(image=filename).apply()
            await utils.save_image(filename, image)
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
    with utils.safe_db_write():
        if patch:
            await item.update(**model.dict(exclude_unset=True)).apply()  # type: ignore
        else:
            await item.update(**model.dict()).apply()
    return item


async def patch_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.AuthDependency(), scopes=["product_management"]),
):
    return await process_edit_product(model_id, data, image, user)


async def put_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.AuthDependency(), scopes=["product_management"]),
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
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
):
    query = models.Product.query
    if sale:
        query = (
            query.select_from(models.Product.join(models.DiscountxProduct).join(models.Discount))
            .having(func.count(models.DiscountxProduct.product_id) > 0)
            .where(models.Discount.end_date > utils.now())
        )
    if store is None:
        user = await utils.AuthDependency()(request, SecurityScopes(["product_management"]))
        query = query.where(models.Product.user_id == user.id)
    else:
        query = query.where(models.Product.store_id == store)
    if category and category != "all":
        query = query.where(models.Product.category == category)
    if min_price is not None:
        query = query.where(models.Product.price >= min_price)
    if max_price is not None:
        query = query.where(models.Product.price <= max_price)
    return await (query.with_only_columns([db.db.func.count(distinct(models.Product.id))]).order_by(None).gino.scalar()) or 0


@router.get("/invoices/order_id/{order_id}", response_model=schemes.DisplayInvoice)
async def get_invoice_by_order_id(order_id: str):
    item = await models.Invoice.query.where(models.Invoice.order_id == order_id).gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with order id {order_id} does not exist!")
    await crud.invoice_add_related(item)
    return item


@router.get("/products/maxprice")
async def get_max_product_price(store: int):
    return (
        await (
            models.Product.query.where(models.Product.store_id == store)
            .with_only_columns([db.db.func.max(distinct(models.Product.price))])
            .order_by(None)
            .gino.scalar()
        )
        or 0
    )


@router.get("/fiatlist")
async def get_fiatlist(query: Optional[str] = None):
    s = None
    for coin in settings.cryptos:
        fiat_list = await settings.cryptos[coin].list_fiat()
        if not s:
            s = set(fiat_list)
        else:
            s = s.intersection(fiat_list)
    if query is not None:
        pattern = re.compile(query, re.IGNORECASE)
        s = [x for x in s if pattern.match(x)]
    return sorted(s)


@router.get("/cryptos")
async def get_cryptos():
    return {
        "count": len(settings.cryptos),
        "next": None,
        "previous": None,
        "result": list(settings.cryptos.keys()),
    }


@router.get("/cryptos/supported")
async def get_supported_cryptos():
    return constants.SUPPORTED_CRYPTOS


@router.get("/notifications/list")
async def get_notifications():
    return {
        "count": len(settings.notifiers),
        "next": None,
        "previous": None,
        "result": list(settings.notifiers.keys()),
    }


@router.get("/notifications/schema")
async def get_notifications_schema():
    return settings.notifiers


@router.get("/templates/list")
async def get_template_list(applicable_to: Optional[str] = None, show_all: bool = False):
    result_set = templates.templates_strings
    if applicable_to:
        result_set = result_set.get(applicable_to, [])
    elif show_all:
        result_set = [v for template_set in result_set.values() for v in template_set]
    return {
        "count": len(result_set),
        "next": None,
        "previous": None,
        "result": result_set,
    }


@router.get("/invoices/export", response_model=List[schemes.DisplayInvoice])
async def export_invoices(
    response: Response,
    export_format: str = "json",
    user: models.User = Security(utils.AuthDependency(), scopes=["invoice_management"]),
):
    data = (
        await models.Invoice.query.where(models.User.id == user.id)
        .where(models.Invoice.status == InvoiceStatus.COMPLETE)
        .gino.all()
    )
    await crud.invoices_add_related(data)
    now = utils.now()
    filename = now.strftime(f"bitcartcc-export-%Y%m%d-%H%M%S.{export_format}")
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    response.headers.update(headers)
    if export_format == "json":
        return data
    else:
        return StreamingResponse(
            iter([export_ext.json_to_csv(export_ext.db_to_json(data)).getvalue()]),
            media_type="application/csv",
            headers=headers,
        )


utils.ModelView.register(
    router,
    "/users",
    models.User,
    schemes.User,
    schemes.CreateUser,
    display_model=schemes.DisplayUser,
    custom_methods={"post": crud.create_user, "patch": crud.patch_user, "put": crud.put_user},
    post_auth=False,
    scopes={
        "get_all": ["server_management"],
        "get_count": ["server_management"],
        "get_one": ["server_management"],
        "post": [],
        "patch": ["server_management"],
        "put": ["server_management"],
        "delete": ["server_management"],
    },
)
utils.ModelView.register(
    router,
    "/wallets",
    models.Wallet,
    schemes.CreateWallet,
    schemes.CreateWallet,
    schemes.Wallet,
    background_tasks_mapping={"post": "sync_wallet"},
    custom_methods={"get": crud.get_wallets, "get_one": crud.get_wallet, "post": crud.create_wallet},
    scopes=["wallet_management"],
)
utils.ModelView.register(
    router,
    "/stores",
    models.Store,
    schemes.Store,
    schemes.CreateStore,
    custom_methods={
        "get": crud.get_stores,
        "get_one": crud.get_store,
        "post": crud.create_store,
        "delete": crud.delete_store,
    },
    get_one_model=None,
    get_one_auth=False,
    scopes=["store_management"],
)
utils.ModelView.register(
    router,
    "/discounts",
    models.Discount,
    schemes.Discount,
    schemes.CreateDiscount,
    custom_methods={"post": crud.create_discount},
    scopes=["discount_management"],
)
utils.ModelView.register(
    router,
    "/notifications",
    models.Notification,
    schemes.Notification,
    schemes.CreateNotification,
    custom_methods={"post": crud.create_notification},
    scopes=["notification_management"],
)
utils.ModelView.register(
    router,
    "/templates",
    models.Template,
    schemes.Template,
    schemes.CreateTemplate,
    custom_methods={"post": crud.create_template},
    scopes=["template_management"],
)
utils.ModelView.register(
    router,
    "/products",
    models.Product,
    schemes.Product,
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
    scopes=["product_management"],
)
utils.ModelView.register(
    router,
    "/invoices",
    models.Invoice,
    schemes.Invoice,
    schemes.CreateInvoice,
    schemes.DisplayInvoice,
    custom_methods={
        "get": crud.get_invoices,
        "get_one": crud.get_invoice,
        "post": crud.create_invoice,
        "delete": crud.delete_invoice,
        "batch_action": crud.batch_invoice_action,
    },
    request_handlers={"get_one": get_invoice_noauth},
    post_auth=False,
    scopes=["invoice_management"],
    custom_commands={"mark_complete": crud.mark_invoice_complete, "mark_invalid": crud.mark_invoice_invalid},
)


@router.get("/crud/stats")
async def get_stats(user: models.User = Security(utils.AuthDependency(), scopes=["full_control"])):
    queries = []
    output_formats = []
    for index, (path, orm_model) in enumerate(utils.ModelView.crud_models):
        query = select([func.count(distinct(orm_model.id))])
        if orm_model != models.User:
            query = query.where(orm_model.user_id == user.id)
        queries.append(query.label(path[1:]))  # remove / from name
        output_formats.append((path[1:], index))
    result = await db.db.first(select(queries))
    response = {key: result[ind] for key, ind in output_formats}
    response.pop("users", None)
    response["balance"] = await get_balances(user)
    return response


@router.get("/rate")
async def rate(currency: str = "btc", fiat_currency: str = "USD"):
    rate = await settings.get_coin(currency).rate(fiat_currency.upper())
    if math.isnan(rate):
        raise HTTPException(422, "Unsupported fiat currency")
    return rate


@router.get("/categories")
async def categories(store: int):
    return {
        category
        for category, in await models.Product.select("category").where(models.Product.store_id == store).gino.all()
        if category
    }.union({"all"})


@router.get("/wallet_history/{model_id}", response_model=List[schemes.TxResponse])
async def wallet_history(
    model_id: int,
    user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"]),
):
    response: List[schemes.TxResponse] = []
    if model_id == 0:
        for model in await models.Wallet.query.gino.all():
            await utils.get_wallet_history(model, response)
    else:
        model = await models.Wallet.query.where(models.Wallet.id == model_id).gino.first()
        if not model:
            raise HTTPException(404, f"Wallet with id {model_id} does not exist!")
        await utils.get_wallet_history(model, response)
    return response


@router.get("/token", response_model=utils.get_pagination_model(schemes.Token))
async def get_tokens(
    user: models.User = Security(utils.AuthDependency(), scopes=["token_management"]),
    pagination: pagination.Pagination = Depends(),
    app_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    permissions: List[str] = Query(None),
):
    return await pagination.paginate(
        models.Token,
        user.id,
        app_id=app_id,
        redirect_url=redirect_url,
        permissions=permissions,
    )


@router.get("/token/current", response_model=schemes.Token)
async def get_current_token(request: Request):
    _, token = await utils.AuthDependency()(request, SecurityScopes(), return_token=True)
    return token


@router.get("/token/count", response_model=int)
async def get_token_count(
    user: models.User = Security(utils.AuthDependency(), scopes=["token_management"]),
    pagination: pagination.Pagination = Depends(),
    app_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    permissions: List[str] = Query(None),
):
    return await pagination.paginate(
        models.Token,
        user.id,
        app_id=app_id,
        redirect_url=redirect_url,
        permissions=permissions,
        count_only=True,
    )


@router.patch("/token/{model_id}", response_model=schemes.Token)
async def patch_token(
    model_id: str,
    model: schemes.EditToken,
    user: models.User = Security(utils.AuthDependency(), scopes=["token_management"]),
):
    item = await models.Token.query.where(models.Token.user_id == user.id).where(models.Token.id == model_id).gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Token with id {model_id} does not exist!")
    with utils.safe_db_write():
        await item.update(**model.dict(exclude_unset=True)).apply()
    return item


@router.delete("/token/{model_id}", response_model=schemes.Token)
async def delete_token(
    model_id: str,
    user: models.User = Security(utils.AuthDependency(), scopes=["token_management"]),
):
    item = await models.Token.query.where(models.Token.user_id == user.id).where(models.Token.id == model_id).gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Token with id {model_id} does not exist!")
    await item.delete()
    return item


@router.post("/token")
async def create_token(
    request: Request,
    token_data: Optional[schemes.HTTPCreateLoginToken] = schemes.HTTPCreateLoginToken(),
):
    token = None
    try:
        user, token = await utils.AuthDependency()(request, SecurityScopes(), return_token=True)
    except HTTPException:
        user, status = await utils.authenticate_user(token_data.email, token_data.password)
        if not user:
            raise HTTPException(401, {"message": "Unauthorized", "status": status})
    token_data = token_data.dict()
    strict = token_data.pop("strict")
    if "server_management" in token_data["permissions"] and not user.is_superuser:
        if strict:
            raise HTTPException(422, "This application requires access to server settings")
        token_data["permissions"].remove("server_management")
    if token and "full_control" not in token.permissions:
        for permission in token_data["permissions"]:
            if permission not in token.permissions:
                raise HTTPException(403, "Not enough permissions")
    token = await models.Token.create(**schemes.CreateDBToken(user_id=user.id, **token_data).dict())
    return {
        **schemes.Token.from_orm(token).dict(),
        "access_token": token.id,
        "token_type": "bearer",
    }


@router.post("/manage/update")
async def update_server(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if settings.DOCKER_ENV:  # pragma: no cover
        utils.run_host("./update.sh")
        return {"status": "success", "message": "Successfully started update process!"}
    return {"status": "error", "message": "Not running in docker"}


@router.post("/manage/cleanup/images")
async def cleanup_images(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if settings.DOCKER_ENV:  # pragma: no cover
        utils.run_host("./cleanup.sh")
        return {"status": "success", "message": "Successfully started cleanup process!"}
    return {"status": "error", "message": "Not running in docker"}


@router.post("/manage/cleanup/logs")
async def cleanup_logs(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if not settings.LOG_DIR:
        return {"status": "error", "message": "Log file unconfigured"}
    for f in os.listdir(settings.LOG_DIR):
        if f.startswith(f"{constants.LOG_FILE_NAME}."):
            try:
                os.remove(os.path.join(settings.LOG_DIR, f))
            except OSError:  # pragma: no cover
                pass
    return {"status": "success", "message": "Successfully started cleanup process!"}


@router.post("/manage/cleanup")
async def cleanup_server(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    data = [await cleanup_images(), await cleanup_logs()]
    message = ""
    for result in data:
        if result["status"] != "success":
            message += f"{result['message']}\n"
        else:
            return {"status": "success", "message": "Successfully started cleanup process!"}
    return {"status": "error", "message": message}


@router.post("/manage/restart")
async def restart_server(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if settings.DOCKER_ENV:  # pragma: no cover
        utils.run_host("./restart.sh")
        return {"status": "success", "message": "Successfully started restart process!"}
    return {"status": "error", "message": "Not running in docker"}


@router.get("/manage/daemons")
async def get_daemons(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    return settings.crypto_settings


@router.get("/manage/policies", response_model=schemes.Policy)
async def get_policies():
    return await utils.get_setting(schemes.Policy)


@router.post("/manage/policies", response_model=schemes.Policy)
async def set_policies(
    settings: schemes.Policy,
    user: models.User = Security(utils.AuthDependency(), scopes=["server_management"]),
):
    return await utils.set_setting(settings)


@router.get("/manage/stores", response_model=schemes.GlobalStorePolicy)
async def get_store_policies():
    return await utils.get_setting(schemes.GlobalStorePolicy)


@router.post("/manage/stores", response_model=schemes.GlobalStorePolicy)
async def set_store_policies(
    settings: schemes.GlobalStorePolicy,
    user: models.User = Security(utils.AuthDependency(), scopes=["server_management"]),
):
    return await utils.set_setting(settings)


@router.get("/services")
async def get_services(request: Request):
    try:
        user = await utils.AuthDependency()(request, SecurityScopes(["server_management"]))
    except HTTPException:
        user = None
    key = "services_dict" if user else "anonymous_services_dict"
    async with utils.wait_for_redis():
        return await tor_ext.get_data(key, {}, json_decode=True)


@router.websocket_route("/ws/wallets/{model_id}")
class WalletNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.wallet_id = int(websocket.path_params["model_id"])
            self.access_token = websocket.query_params["token"]
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        try:
            self.user = await utils.AuthDependency(token=self.access_token)(None, SecurityScopes(["wallet_management"]))
        except HTTPException:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.wallet = (
            await models.Wallet.query.where(models.Wallet.id == self.wallet_id)
            .where(models.Wallet.user_id == self.user.id)
            .gino.first()
        )
        if not self.wallet:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.subscriber, self.channel = await utils.make_subscriber(f"wallet:{self.wallet_id}")
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:wallet:{self.wallet_id}")


@router.websocket_route("/ws/invoices/{model_id}")
class InvoiceNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.invoice_id = int(websocket.path_params["model_id"])
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.invoice = await models.Invoice.query.where(models.Invoice.id == self.invoice_id).gino.first()
        if not self.invoice:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if self.invoice.status in [InvoiceStatus.EXPIRED, InvoiceStatus.COMPLETE]:
            await websocket.send_json({"status": self.invoice.status})
            await websocket.close()
            return
        self.invoice = await crud.get_invoice(self.invoice_id, None, self.invoice)
        self.subscriber, self.channel = await utils.make_subscriber(f"invoice:{self.invoice_id}")
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:invoice:{self.invoice_id}")


@router.get("/updatecheck")
async def check_updates():
    async with utils.wait_for_redis():
        new_update_tag = await settings.redis_pool.hget(update_ext.REDIS_KEY, "new_update_tag")
        return {"update_available": bool(new_update_tag), "tag": new_update_tag}


@router.get("/manage/logs")
async def get_logs_list(user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if not settings.LOG_DIR:
        return []
    data = sorted([f for f in os.listdir(settings.LOG_DIR) if f.startswith(f"{constants.LOG_FILE_NAME}.")], reverse=True)
    if os.path.exists(os.path.join(settings.LOG_DIR, constants.LOG_FILE_NAME)):
        data = [constants.LOG_FILE_NAME] + data
    return data


@router.get("/manage/logs/{log}")
async def get_log_contents(log: str, user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if not settings.LOG_DIR:
        raise HTTPException(400, "Log file unconfigured")
    try:
        with open(os.path.join(settings.LOG_DIR, log)) as f:
            contents = f.read()
        return contents
    except OSError:
        raise HTTPException(404, "This log doesn't exist")


@router.delete("/manage/logs/{log}")
async def delete_log(log: str, user: models.User = Security(utils.AuthDependency(), scopes=["server_management"])):
    if not settings.LOG_DIR:
        raise HTTPException(400, "Log file unconfigured")
    if log == constants.LOG_FILE_NAME:
        raise HTTPException(403, "Forbidden to delete current log file")
    try:
        os.remove(os.path.join(settings.LOG_DIR, log))
        return True
    except OSError:
        raise HTTPException(404, "This log doesn't exist")


@router.get("/wallets/{model_id}/balance")
async def get_wallet_balance(
    model_id: int, user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"])
):
    coin = await crud.get_wallet_coin_by_id(model_id)
    return await coin.balance()


@router.get("/wallets/{model_id}/checkln")
async def check_wallet_lightning(
    model_id: int, user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"])
):
    try:
        coin = await crud.get_wallet_coin_by_id(model_id)
        return await coin.node_id
    except BitcartBaseError:
        return False


@router.get("/wallets/{model_id}/channels")
async def get_wallet_channels(
    model_id: int, user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"])
):
    try:
        coin = await crud.get_wallet_coin_by_id(model_id)
        return await coin.list_channels()
    except BitcartBaseError:
        return []


@router.post("/wallets/{model_id}/channels/open")
async def open_wallet_channel(
    model_id: int,
    params: schemes.OpenChannelScheme,
    user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"]),
):
    try:
        coin = await crud.get_wallet_coin_by_id(model_id)
        return await coin.open_channel(params.node_id, params.amount)
    except BitcartBaseError:
        raise HTTPException(400, "Failed to open channel")


@router.post("/wallets/{model_id}/channels/close")
async def close_wallet_channel(
    model_id: int,
    params: schemes.CloseChannelScheme,
    user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"]),
):
    try:
        coin = await crud.get_wallet_coin_by_id(model_id)
        return await coin.close_channel(params.channel_point, force=params.force)
    except BitcartBaseError:
        raise HTTPException(400, "Failed to close channel")


@router.post("/wallets/{model_id}/lnpay")
async def wallet_lnpay(
    model_id: int,
    params: schemes.LNPayScheme,
    user: models.User = Security(utils.AuthDependency(), scopes=["wallet_management"]),
):
    try:
        coin = await crud.get_wallet_coin_by_id(model_id)
        return await coin.lnpay(params.invoice)
    except BitcartBaseError:
        raise HTTPException(400, "Failed to pay the invoice")


@router.post("/configurator/deploy")
async def generate_deployment(settings: schemes.ConfiguratorDeploySettings, request: Request):
    await configurator.authenticate_request(request)
    script = configurator.create_bash_script(settings)
    return await configurator.create_new_task(script, settings.ssh_settings, settings.mode == "Manual")


@router.get("/configurator/deploy-result/{deploy_id}")
async def get_deploy_result(deploy_id: str, request: Request):
    await configurator.authenticate_request(request)
    data = await configurator.get_task(deploy_id)
    if not data:
        raise HTTPException(404, f"Deployment result {deploy_id} does not exist!")
    return data
