# pylint: disable=no-member, no-name-in-module
import json
import os
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from os.path import join as path_join
from typing import Callable, Dict, List, Optional, Type, Union

import aioredis
import asyncpg
import notifiers
from aiohttp import ClientSession
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jinja2 import Template
from passlib.context import CryptContext
from pydantic import BaseModel
from pydantic import create_model as create_pydantic_model
from sqlalchemy import distinct
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from . import db, exceptions, models, pagination, settings, templates


async def make_subscriber(name):
    subscriber = await aioredis.create_redis_pool(settings.REDIS_HOST)
    res = await subscriber.subscribe(f"channel:{name}")
    channel = res[0]
    return subscriber, channel


async def publish_message(channel, message):
    return await settings.redis_pool.publish_json(f"channel:{channel}", message)


def now():
    return datetime.now(timezone.utc)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(email: str, password: str):
    user = await models.User.query.where(models.User.email == email).gino.first()
    if not user:
        return False, 404
    if not verify_password(password, user.hashed_password):
        return False, 401
    return user, 200


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "server_management": "Edit server settings",
        "token_management": "Create, list or edit tokens",
        "wallet_management": "Create, list or edit wallets",
        "store_management": "Create, list or edit stores",
        "discount_management": "Create, list or edit discounts",
        "product_management": "Create, list or edit products",
        "invoice_management": "Create, list or edit invoices",
        "notification_management": "Create, list or edit notification providers",
        "template_management": "Create, list or edit templates",
        "full_control": "Full control over what current user has",
    },
)


def check_selective_scopes(request, scope, token):
    model_id = request.path_params.get("model_id", None)
    if model_id is None:
        return False
    return f"{scope}:{model_id}" in token.permissions


class AuthDependency:
    def __init__(self, enabled: bool = True, token: Optional[str] = None):
        self.enabled = enabled
        self.token = token

    async def __call__(
        self, request: Request, security_scopes: SecurityScopes, return_token=False
    ):
        if not self.enabled:
            return None
        if security_scopes.scopes:
            authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
        else:
            authenticate_value = f"Bearer"
        token: str = await oauth2_scheme(request) if not self.token else self.token
        data = (
            await models.User.join(models.Token)
            .select(models.Token.id == token)
            .gino.load((models.User, models.Token))
            .first()
        )
        if data is None:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": authenticate_value},
            )
        user, token = data  # first validate data, then unpack
        forbidden_exception = HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )
        if "full_control" not in token.permissions:
            for scope in security_scopes.scopes:
                if scope not in token.permissions and not check_selective_scopes(
                    request, scope, token
                ):
                    raise forbidden_exception
        if "server_management" in security_scopes.scopes and not user.is_superuser:
            raise forbidden_exception
        if return_token:
            return user, token
        return user


HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
ENDPOINTS: List[str] = [
    "get_all",
    "get_one",
    "get_count",
    "post",
    "put",
    "patch",
    "delete",
]
crud_models = []


def model_view(
    router: APIRouter,
    path: str,
    orm_model,
    pydantic_model,
    create_model=None,
    display_model=None,
    allowed_methods: List[str] = ["GET_COUNT", "GET_ONE"] + HTTP_METHODS,
    custom_methods: Dict[str, Callable] = {},
    background_tasks_mapping: Dict[str, Callable] = {},
    request_handlers: Dict[str, Callable] = {},
    auth=True,
    get_one_auth=True,
    post_auth=True,
    get_one_model=True,
    scopes=None,
):
    from . import schemes

    if scopes is None:
        scopes = {i: [] for i in ENDPOINTS}
    crud_models.append((path, orm_model))

    display_model = pydantic_model if not display_model else display_model
    if isinstance(scopes, list):
        scopes_list = scopes.copy()
        scopes = {i: scopes_list for i in ENDPOINTS}
    scopes = defaultdict(list, **scopes)

    PaginationResponse = create_pydantic_model(
        f"PaginationResponse_{display_model.__name__}",
        count=(int, ...),
        next=(Optional[str], None),
        previous=(Optional[str], None),
        result=(List[display_model], ...),
        __base__=BaseModel,
    )

    if not create_model:
        create_model = pydantic_model  # pragma: no cover
    response_models: Dict[str, Type] = {
        "get": PaginationResponse,
        "get_count": int,
        "get_one": display_model if get_one_model else None,
        "post": display_model,
        "put": display_model,
        "patch": display_model,
        "delete": display_model,
    }

    item_path = path_join(path, "{model_id}")
    count_path = path_join(path, "count")
    paths: Dict[str, str] = {
        "get": path,
        "get_count": count_path,
        "get_one": item_path,
        "post": path,
        "put": item_path,
        "patch": item_path,
        "delete": item_path,
    }

    auth_dependency = AuthDependency(auth)

    async def _get_one(model_id: int, user: schemes.User, internal: bool = False):
        query = orm_model.query
        if orm_model != models.User and user:
            query = query.where(orm_model.user_id == user.id)
        item = await query.where(orm_model.id == model_id).gino.first()
        if custom_methods.get("get_one"):
            item = await custom_methods["get_one"](model_id, user, item, internal)
        if not item:
            raise HTTPException(
                status_code=404, detail=f"Object with id {model_id} does not exist!"
            )
        return item

    async def get(
        pagination: pagination.Pagination = Depends(),
        user: Union[None, schemes.User] = Security(
            auth_dependency, scopes=scopes["get_all"]
        ),
    ):
        if custom_methods.get("get"):
            return await custom_methods["get"](pagination, user)
        else:
            return await pagination.paginate(orm_model, user.id)

    async def get_count(
        user: Union[None, schemes.User] = Security(
            auth_dependency, scopes=scopes["get_count"]
        )
    ):
        return (
            await (
                (
                    orm_model.query.where(orm_model.user_id == user.id)
                    if orm_model != models.User
                    else orm_model.query
                )
                .with_only_columns([db.db.func.count(distinct(orm_model.id))])
                .order_by(None)
                .gino.scalar()
            )
            or 0
        )

    async def get_one(model_id: int, request: Request):
        try:
            user = await auth_dependency(request, SecurityScopes(scopes["get_one"]))
        except HTTPException:
            if get_one_auth:
                raise
            user = None
        return await _get_one(model_id, user)

    async def post(
        model: create_model, request: Request,  # type: ignore,
    ):
        try:
            user = await auth_dependency(request, SecurityScopes(scopes["post"]))
        except HTTPException:
            if post_auth:
                raise
            user = None
        try:
            if custom_methods.get("post"):
                obj = await custom_methods["post"](model, user)
            else:
                obj = await orm_model.create(**model.dict())  # type: ignore
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
            asyncpg.exceptions.ForeignKeyViolationError,
        ) as e:
            raise HTTPException(422, e.message)
        if background_tasks_mapping.get("post"):
            background_tasks_mapping["post"].send(obj.id)
        return obj

    async def put(
        model_id: int,
        model: pydantic_model,
        user: Union[None, schemes.User] = Security(
            auth_dependency, scopes=scopes["put"]
        ),
    ):  # type: ignore
        item = await _get_one(model_id, user, True)
        try:
            if custom_methods.get("put"):
                await custom_methods["put"](item, model, user)  # pragma: no cover
            else:
                await item.update(**model.dict()).apply()  # type: ignore
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
            asyncpg.exceptions.ForeignKeyViolationError,
        ) as e:
            raise HTTPException(422, e.message)
        return item

    async def patch(
        model_id: int,
        model: pydantic_model,
        user: Union[None, schemes.User] = Security(
            auth_dependency, scopes=scopes["patch"]
        ),
    ):  # type: ignore
        item = await _get_one(model_id, user, True)
        try:
            if custom_methods.get("patch"):
                await custom_methods["patch"](item, model, user)  # pragma: no cover
            else:
                await item.update(
                    **model.dict(exclude_unset=True)  # type: ignore
                ).apply()
        except (  # pragma: no cover
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
            asyncpg.exceptions.ForeignKeyViolationError,
        ) as e:
            raise HTTPException(422, e.message)  # pragma: no cover
        return item

    async def delete(
        model_id: int,
        user: Union[None, schemes.User] = Security(
            auth_dependency, scopes=scopes["delete"]
        ),
    ):
        item = await _get_one(model_id, user, True)
        if custom_methods.get("delete"):
            await custom_methods["delete"](item, user)
        else:
            await item.delete()
        return item

    for method in allowed_methods:
        method_name = method.lower()
        router.add_api_route(
            paths.get(method_name),  # type: ignore
            request_handlers.get(method_name) or locals()[method_name],
            methods=[method_name if method in HTTP_METHODS else "get"],
            response_model=response_models.get(method_name),
        )


async def get_wallet_history(model, response):
    coin = settings.get_coin(model.currency, model.xpub)
    txes = (await coin.history())["transactions"]
    for i in txes:
        response.append({"date": i["date"], "txid": i["txid"], "amount": i["bc_value"]})


def check_ping(host, port, user, password, email, ssl=True):
    try:
        server = smtplib.SMTP(host=host, port=port, timeout=2)
        if ssl:
            server.starttls()
        server.login(user, password)
        server.verify(email)
        server.quit()
        return True
    except OSError:
        return False


async def get_template(name, user_id=None):
    query = models.Template.query.where(models.Template.name == name)
    if user_id:
        query = query.where(models.Template.user_id == user_id)
    custom_template = await query.gino.first()
    if custom_template:
        return templates.Template(name, custom_template.text)
    if name in templates.templates:
        return templates.templates[name]
    raise exceptions.TemplateDoesNotExistError(
        f"Template {name} does not exist and has no default"
    )


async def get_product_template(store, product, quantity):
    template = await get_template("email_product", store.user_id)
    return template.render(store=store, product=product, quantity=quantity)


async def get_store_template(store, products):
    template = await get_template("email_base_shop", store.user_id)
    return template.render(store=store, products=products)


def send_mail(store, where, message, subject="Thank you for your purchase"):
    message = f"Subject: {subject}\n\n{message}"
    server = smtplib.SMTP(host=store.email_host, port=store.email_port, timeout=2)
    if store.email_use_ssl:
        server.starttls()
    server.login(store.email_user, store.email_password)
    server.sendmail(store.email, where, message)
    server.quit()


def get_image_filename(image, create=True, model=None):
    filename = None
    if create:
        filename = "images/products/temp.png" if image else None
    else:
        if image:
            filename = f"images/products/{model.id}.png"
        else:
            filename = model.image
    return filename


async def save_image(filename, image):
    with open(filename, "wb") as f:
        f.write(await image.read())


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass


async def send_ipn(obj, status):
    if obj.notification_url:
        data = {"id": obj.id, "status": status}
        try:
            async with ClientSession() as session:
                await session.post(obj.notification_url, json=data)
        except Exception:
            pass


def run_host(command):
    if not os.path.exists("queue"):
        raise HTTPException(422, "No pipe existing")
    with open("queue", "w") as f:
        f.write(f"{command}\n")


async def get_setting(scheme):
    name = scheme.__name__.lower()
    item = await models.Setting.query.where(models.Setting.name == name).gino.first()
    if not item:
        return scheme()
    return scheme(**json.loads(item.value))


async def set_setting(scheme):
    name = scheme.__class__.__name__.lower()
    json_data = scheme.dict(exclude_unset=True)
    data = {"name": name, "value": json_data}
    model = await models.Setting.query.where(models.Setting.name == name).gino.first()
    if model:
        value = json.loads(model.value)
        for key in json_data:
            value[key] = json_data[key]
        data["value"] = json.dumps(value)
        await model.update(**data).apply()
    else:
        data["value"] = json.dumps(json_data)
        await models.Setting.create(**data)
    return scheme


def get_pagination_model(display_model):
    return create_pydantic_model(
        f"PaginationResponse_{display_model.__name__}",
        count=(int, ...),
        next=(Optional[str], None),
        previous=(Optional[str], None),
        result=(List[display_model], ...),
        __base__=BaseModel,
    )


async def notify(store, text):
    notification_providers = [
        await models.Notification.get(notification_id)
        for notification_id in store.notifications
    ]
    for provider in notification_providers:
        notifiers.notify(provider.provider, message=text, **provider.data)


async def get_notify_template(store, invoice):
    template = await get_template("notification", store.user_id)
    return template.render(store=store, invoice=invoice)
