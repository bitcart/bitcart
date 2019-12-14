# pylint: disable=no-member
import smtplib
from datetime import datetime, timedelta
from os.path import join as path_join
from typing import Callable, Dict, List, Optional, Type, Union

import aioredis
import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jinja2 import Template
from jwt import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from pytz import utc
from sqlalchemy import distinct
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from bitcart import BTC

from . import db, models, pagination, settings


async def make_subscriber(name):
    subscriber = await aioredis.create_redis_pool(settings.REDIS_HOST)
    res = await subscriber.subscribe(f"channel:{name}")
    channel = res[0]
    return subscriber, channel


async def publish_message(channel, message):
    return await settings.redis_pool.publish_json(f"channel:{channel}", message)


def now():
    return datetime.utcnow().replace(tzinfo=utc)


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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def create_access_token(
    *, data: dict, token_type: str, expires_delta: timedelta = timedelta(minutes=15)
):
    to_encode = data.copy()
    expire = now() + expires_delta
    to_encode.update({"exp": expire, "token_type": token_type})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


class AuthDependency:
    def __init__(
        self,
        enabled: bool = True,
        superuser_only: bool = False,
        token: Optional[str] = None,
        token_type: str = "access",
    ):
        self.enabled = enabled
        self.superuser_only = superuser_only
        self.token = token
        self.token_type = token_type

    async def __call__(self, request: Request):
        if not self.enabled:
            return None
        token: str = await oauth2_scheme(request) if not self.token else self.token
        from . import schemes

        credentials_exception = HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_type: str = payload.get("token_type")
            email: str = payload.get("sub")
            if token_type != self.token_type or email is None:
                raise credentials_exception
            token_data = schemes.TokenData(email=email)
        except PyJWTError:
            raise credentials_exception
        user = await models.User.query.where(
            models.User.email == token_data.email
        ).gino.first()
        if user is None:
            raise credentials_exception
        if self.superuser_only and not user.is_superuser:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )
        return user


HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def model_view(
    router: APIRouter,
    path: str,
    orm_model,
    pydantic_model,
    get_data_source,
    create_model=None,
    display_model=None,
    allowed_methods: List[str] = ["GET_COUNT", "GET_ONE"] + HTTP_METHODS,
    custom_methods: Dict[str, Callable] = {},
    background_tasks_mapping: Dict[str, Callable] = {},
    request_handlers: Dict[str, Callable] = {},
    auth=True,
):
    from . import schemes

    display_model = pydantic_model if not display_model else display_model

    class PaginationResponse(BaseModel):
        count: int
        next: Optional[str]
        previous: Optional[str]
        result: List[display_model]  # type: ignore

    if not create_model:
        create_model = pydantic_model  # pragma: no cover
    response_models: Dict[str, Type] = {
        "get": PaginationResponse,
        "get_count": int,
        "get_one": display_model,
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

    auth_dependency = AuthDependency(auth, create_model == schemes.CreateUser)

    async def get(
        pagination: pagination.Pagination = Depends(),
        user: Union[None, schemes.User] = Depends(auth_dependency),
    ):
        if custom_methods.get("get"):
            return await custom_methods["get"](pagination, user, get_data_source())
        else:
            return await pagination.paginate(orm_model, get_data_source(), user.id)

    async def get_count(user: Union[None, schemes.User] = Depends(auth_dependency)):
        return await (
            (
                orm_model.query.select_from(get_data_source()).where(
                    models.User.id == user.id
                )
                if orm_model != models.User
                else orm_model.query
            )
            .with_only_columns([db.db.func.count(distinct(orm_model.id))])
            .order_by(None)
            .gino.scalar()
        )

    async def get_one(
        model_id: int, user: Union[None, schemes.User] = Depends(auth_dependency)
    ):
        item = await (
            (
                orm_model.query.select_from(get_data_source())
                if orm_model != models.User
                else orm_model.query
            )
            .where(orm_model.id == model_id)
            .gino.first()
        )
        if custom_methods.get("get_one"):
            item = await custom_methods["get_one"](model_id, user, item)
        if not item:
            raise HTTPException(
                status_code=404, detail=f"Object with id {model_id} does not exist!"
            )
        return item

    async def post(
        model: create_model,  # type: ignore,
        request: Request,
    ):
        try:
            user = await auth_dependency(request)
        except HTTPException:
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
        user: Union[None, schemes.User] = Depends(auth_dependency),
    ):  # type: ignore
        item = await get_one(model_id)
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
        user: Union[None, schemes.User] = Depends(auth_dependency),
    ):  # type: ignore
        item = await get_one(model_id)
        try:
            if custom_methods.get("patch"):
                await custom_methods["patch"](item, model, user)  # pragma: no cover
            else:
                await item.update(
                    **model.dict(skip_defaults=True)  # type: ignore
                ).apply()
        except (  # pragma: no cover
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
            asyncpg.exceptions.ForeignKeyViolationError,
        ) as e:
            raise HTTPException(422, e.message)  # pragma: no cover
        return item

    async def delete(
        model_id: int, user: Union[None, schemes.User] = Depends(auth_dependency)
    ):
        item = await get_one(model_id)
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
    btc = BTC(
        settings.RPC_URL,
        xpub=model.xpub,
        rpc_user=settings.RPC_USER,
        rpc_pass=settings.RPC_PASS,
    )
    txes = (await btc.history())["transactions"]
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


def get_email_template(store, product):
    with open("api/templates/email_product.j2") as f:
        template = Template(f.read())
    return template.render(store=store, product=product)


def send_mail(store, where, message):
    server = smtplib.SMTP(host=store.email_host, port=store.email_port, timeout=2)
    if store.email_use_ssl:
        server.starttls()
    server.login(store.email_user, store.email_password)
    server.sendmail(store.email, where, message)
    server.quit()
