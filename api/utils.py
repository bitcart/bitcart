import asyncio
import inspect
import json
import os
import smtplib
import traceback
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os.path import join as path_join
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type, Union

import aioredis
import asyncpg
import notifiers
from aiohttp import ClientSession
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from passlib.context import CryptContext
from pydantic import BaseModel
from pydantic import create_model as create_pydantic_model
from sqlalchemy import distinct
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from . import db, exceptions, models, pagination, settings, templates
from .logger import get_logger

logger = get_logger(__name__)


async def make_subscriber(name):
    subscriber = await aioredis.create_redis_pool(settings.REDIS_HOST)
    res = await subscriber.subscribe(f"channel:{name}")
    channel = res[0]
    return subscriber, channel


async def publish_message(channel, message):
    async with wait_for_redis():
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

    async def __call__(self, request: Request, security_scopes: SecurityScopes, return_token=False):
        if not self.enabled:
            return None
        if security_scopes.scopes:
            authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
        else:
            authenticate_value = "Bearer"
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
                if scope not in token.permissions and not check_selective_scopes(request, scope, token):
                    raise forbidden_exception
        if "server_management" in security_scopes.scopes and not user.is_superuser:
            raise forbidden_exception
        if return_token:
            return user, token
        return user


HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
ENDPOINTS: List[str] = ["get_all", "get_one", "get_count", "post", "put", "patch", "delete", "batch_action"]
CUSTOM_HTTP_METHODS: dict = {"batch_action": "post"}


@dataclass
class ModelView:
    from . import schemes

    crud_models: ClassVar[list] = []

    router: APIRouter
    path: str
    orm_model: db.db.Model
    create_model: Any
    pydantic_model: Any
    display_model: Any
    allowed_methods: List[str]
    custom_methods: Dict[str, Callable]
    background_tasks_mapping: Dict[str, Callable]
    request_handlers: Dict[str, Callable]
    auth_dependency: AuthDependency
    get_one_auth: bool
    post_auth: bool
    get_one_model: bool
    scopes: Union[List, Dict]
    custom_commands: Dict[str, Callable]

    @classmethod
    def register(
        cls,
        router: APIRouter,
        path: str,
        orm_model,
        pydantic_model,
        create_model=None,
        display_model=None,
        allowed_methods: List[str] = ["GET_COUNT", "GET_ONE"] + HTTP_METHODS + ["BATCH_ACTION"],
        custom_methods: Dict[str, Callable] = {},
        background_tasks_mapping: Dict[str, Callable] = {},
        request_handlers: Dict[str, Callable] = {},
        auth=True,
        get_one_auth=True,
        post_auth=True,
        get_one_model=True,
        scopes=None,
        custom_commands={},
    ):
        # add to crud_models
        if scopes is None:  # pragma: no cover
            scopes = {i: [] for i in ENDPOINTS}
        cls.crud_models.append((path, orm_model))
        # set scopes
        if isinstance(scopes, list):
            scopes_list = scopes.copy()
            scopes = {i: scopes_list for i in ENDPOINTS}
        scopes = defaultdict(list, **scopes)

        if not create_model:
            create_model = pydantic_model  # pragma: no cover
        cls(
            router=router,
            path=path,
            orm_model=orm_model,
            pydantic_model=pydantic_model,
            create_model=create_model,
            display_model=display_model,
            allowed_methods=allowed_methods,
            custom_methods=custom_methods,
            background_tasks_mapping=background_tasks_mapping,
            request_handlers=request_handlers,
            auth_dependency=AuthDependency(auth),
            get_one_auth=get_one_auth,
            post_auth=post_auth,
            get_one_model=get_one_model,
            scopes=scopes,
            custom_commands=custom_commands,
        ).register_routes()

    def register_routes(self):
        response_models = self.get_response_models()
        paths = self.get_paths()
        for method in self.allowed_methods:
            method_name = method.lower()
            self.router.add_api_route(
                paths.get(method_name),  # type: ignore
                self.request_handlers.get(method_name)
                or getattr(self, method_name, None)
                or getattr(self, f"_{method_name}")(),
                methods=[method_name if method in HTTP_METHODS else CUSTOM_HTTP_METHODS.get(method_name, "get")],
                response_model=response_models.get(method_name),
            )

    def get_paths(self) -> Dict[str, str]:
        item_path = path_join(self.path, "{model_id}")
        batch_path = path_join(self.path, "batch")
        count_path = path_join(self.path, "count")
        return {
            "get": self.path,
            "get_count": count_path,
            "get_one": item_path,
            "post": self.path,
            "put": item_path,
            "patch": item_path,
            "delete": item_path,
            "batch_action": batch_path,
        }

    def get_response_models(self) -> Dict[str, Type]:
        display_model = self.pydantic_model if not self.display_model else self.display_model
        pagination_response = create_pydantic_model(
            f"PaginationResponse_{display_model.__name__}",
            count=(int, ...),
            next=(Optional[str], None),
            previous=(Optional[str], None),
            result=(List[display_model], ...),
            __base__=BaseModel,
        )
        return {
            "get": pagination_response,
            "get_count": int,
            "get_one": display_model if self.get_one_model else None,
            "post": display_model,
            "put": display_model,
            "patch": display_model,
            "delete": display_model,
        }

    async def _get_one(self, model_id: int, user: schemes.User, internal: bool = False):
        query = self.orm_model.query
        if self.orm_model != models.User and user:
            query = query.where(self.orm_model.user_id == user.id)
        item = await query.where(self.orm_model.id == model_id).gino.first()
        if self.custom_methods.get("get_one"):
            item = await self.custom_methods["get_one"](model_id, user, item, internal)
        if not item:
            raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
        return item

    def _get(self):
        async def get(
            pagination: pagination.Pagination = Depends(),
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["get_all"]),
        ):
            if self.custom_methods.get("get"):
                return await self.custom_methods["get"](pagination, user)
            else:
                return await pagination.paginate(self.orm_model, user.id)

        return get

    def _get_count(self):
        async def get_count(
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["get_count"])
        ):
            return (
                await (
                    (
                        self.orm_model.query.where(self.orm_model.user_id == user.id)
                        if self.orm_model != models.User
                        else self.orm_model.query
                    )
                    .with_only_columns([db.db.func.count(distinct(self.orm_model.id))])
                    .order_by(None)
                    .gino.scalar()
                )
                or 0
            )

        return get_count

    async def get_one(self, model_id: int, request: Request):
        try:
            user = await self.auth_dependency(request, SecurityScopes(self.scopes["get_one"]))
        except HTTPException:
            if self.get_one_auth:
                raise
            user = None
        return await self._get_one(model_id, user)

    def _post(self):
        async def post(model: self.create_model, request: Request, background_tasks: BackgroundTasks):
            try:
                user = await self.auth_dependency(request, SecurityScopes(self.scopes["post"]))
            except HTTPException:
                if self.post_auth:
                    raise
                user = None
            with safe_db_write():
                if self.custom_methods.get("post"):
                    obj = await self.custom_methods["post"](model, user)
                else:
                    obj = await self.orm_model.create(**model.dict())  # type: ignore # pragma: no cover
            if self.background_tasks_mapping.get("post"):
                background_tasks.add_task(self.background_tasks_mapping["post"], obj.id)
            return obj

        return post

    def _put(self):
        async def put(
            model_id: int,
            model: self.pydantic_model,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["put"]),
        ):  # type: ignore
            item = await self._get_one(model_id, user, True)
            with safe_db_write():
                if self.custom_methods.get("put"):
                    await self.custom_methods["put"](item, model, user)  # pragma: no cover
                else:
                    await item.update(**model.dict()).apply()  # type: ignore
            return item

        return put

    def _patch(self):
        async def patch(
            model_id: int,
            model: self.pydantic_model,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["patch"]),
        ):  # type: ignore
            item = await self._get_one(model_id, user, True)
            with safe_db_write():
                if self.custom_methods.get("patch"):
                    await self.custom_methods["patch"](item, model, user)  # pragma: no cover
                else:
                    await item.update(**model.dict(exclude_unset=True)).apply()  # type: ignore
            return item

        return patch

    def _delete(self):
        async def delete(
            model_id: int,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["delete"]),
        ):
            item = await self._get_one(model_id, user, True)
            if self.custom_methods.get("delete"):
                await self.custom_methods["delete"](item, user)
            else:
                await item.delete()
            return item

        return delete

    def process_command(self, command):
        if command in self.custom_commands:
            return self.custom_commands[command](self.orm_model)
        if command == "delete":
            return self.orm_model.delete

    def _batch_action(self):
        async def batch_action(
            settings: ModelView.schemes.BatchSettings,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["batch_action"]),
        ):
            query = self.process_command(settings.command)
            if query is None:
                raise HTTPException(status_code=404, detail="Batch command not found")
            if self.orm_model != models.User and user:
                query = query.where(self.orm_model.user_id == user.id)
            query = query.where(self.orm_model.id.in_(settings.ids))
            if self.custom_methods.get("batch_action"):
                await self.custom_methods["batch_action"](query, settings.ids, user)  # pragma: no cover
            else:
                await query.gino.status()
            return True

        return batch_action


async def get_wallet_history(model, response):
    coin = settings.get_coin(model.currency, model.xpub)
    txes = (await coin.history())["transactions"]
    for i in txes:
        response.append({"date": i["date"], "txid": i["txid"], "amount": i["bc_value"]})


def get_email_dsn(host, port, user, password, email, ssl=True):
    return f"{user}:{password}@{host}:{port}?email={email}&ssl={ssl}"


def check_ping(host, port, user, password, email, ssl=True):  # pragma: no cover
    dsn = get_email_dsn(host, port, user, password, email, ssl)
    if not (host and port and user and password and email):
        logger.debug("Checking ping failed: some parameters empty")
        return False
    try:
        server = smtplib.SMTP(host=host, port=port, timeout=2)
        if ssl:
            server.starttls()
        server.login(user, password)
        server.verify(email)
        server.quit()
        logger.debug(f"Checking ping successful for {dsn}")
        return True
    except OSError:
        logger.debug(f"Checking ping error for {dsn}\n{traceback.format_exc()}")
        return False


def get_object_name(obj):
    return obj.__class__.__name__.lower()


def get_template_matching_str(name, obj):
    template_str = f'Template matching "{name}"'
    if obj and hasattr(obj, "id"):
        template_str += f" for {get_object_name(obj)} {obj.id}"
    template_str += ":"
    return template_str


async def get_template(name, user_id=None, obj=None):
    if obj and obj.templates.get(name):
        query = models.Template.query.where(models.Template.id == obj.templates[name])
    else:
        query = models.Template.query.where(models.Template.name == name)
    if user_id:
        query = query.where(models.Template.user_id == user_id)
    custom_template = await query.gino.first()
    if custom_template:
        logger.info(f"{get_template_matching_str(name,obj)} selected custom template " f'"{custom_template.name}"')
        return templates.Template(name, custom_template.text)
    if name in templates.templates:
        logger.info(f"{get_template_matching_str(name,obj)} selected default template")
        return templates.templates[name]
    raise exceptions.TemplateDoesNotExistError(f"Template {name} does not exist and has no default")


async def get_product_template(store, product, quantity):
    template = await get_template("product", store.user_id, product)
    return template.render(store=store, product=product, quantity=quantity)


async def get_store_template(store, products):
    template = await get_template("shop", store.user_id, store)
    return template.render(store=store, products=products)


def send_mail(store, where, text, subject="Thank you for your purchase"):  # pragma: no cover
    message_obj = MIMEMultipart()
    message_obj["Subject"] = subject
    message_obj["From"] = store.email
    message_obj["To"] = where
    message_obj.attach(MIMEText(text, "html" if store.use_html_templates else "plain"))
    message = message_obj.as_string()
    server = smtplib.SMTP(host=store.email_host, port=store.email_port, timeout=2)
    if store.email_use_ssl:
        server.starttls()
    server.login(store.email_user, store.email_password)
    server.sendmail(store.email, where, message)
    server.quit()


def get_image_filename(image, create=True, model=None):
    if create:
        filename = "images/products/temp.png" if image else None
    else:
        filename = f"images/products/{model.id}.png" if image else model.image
    return filename


async def save_image(filename, image):
    with open(filename, "wb") as f:
        f.write(await image.read())


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass


async def send_ipn(obj, status):  # pragma: no cover
    if obj.notification_url:
        data = {"id": obj.id, "status": status}
        try:
            async with ClientSession() as session:
                await session.post(obj.notification_url, json=data)
        except Exception:
            pass


def run_host(command, target_file="queue"):
    if not os.path.exists(target_file):
        raise HTTPException(422, "No pipe existing")
    with open(target_file, "w") as f:
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
        await models.Setting.create(**data, created=now())
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


async def notify(store, text):  # pragma: no cover
    notification_providers = [await models.Notification.get(notification_id) for notification_id in store.notifications]
    for provider in notification_providers:
        notifiers.notify(provider.provider, message=text, **provider.data)


async def get_notify_template(store, invoice):
    template = await get_template("notification", store.user_id, store)
    return template.render(store=store, invoice=invoice)


async def run_repeated(func, timeout, start_timeout=None):  # pragma: no cover
    if not start_timeout:
        start_timeout = timeout
    first_iter = True
    while True:
        await asyncio.sleep(start_timeout if first_iter else timeout)
        result = func()
        if inspect.isawaitable(result):  # pragma: no cover
            await result
        first_iter = False


def time_diff(dt):
    return max(0, int(round(dt.days * 86400 + dt.seconds)))


@contextmanager
def safe_db_write():
    try:
        yield
    except asyncpg.exceptions.IntegrityConstraintViolationError as e:
        raise HTTPException(422, e.message)


async def get_wallet_balance(coin):
    return (await coin.balance())["confirmed"]


class WaitForRedis:  # pragma: no cover
    async def __aenter__(self):
        while not settings.redis_pool:
            await asyncio.sleep(0.01)

    async def __aexit__(self, exc_type, exc, tb):
        pass


wait_for_redis = WaitForRedis
