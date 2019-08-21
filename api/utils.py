from datetime import datetime
from os.path import join as path_join
from typing import Callable, Dict, List, Type, Union

import asyncpg
from bitcart_async import BTC
from fastapi import APIRouter, BackgroundTasks, HTTPException
from passlib.context import CryptContext
from pytz import utc

from . import models, settings


def now():
    return datetime.utcnow().replace(tzinfo=utc)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(username: str, password: str):
    user = await models.User.query.where(models.User.username == username).gino.first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def model_view(
    router: APIRouter,
    path: str,
    orm_model,
    pydantic_model,
    create_model=None,
    allowed_methods: List[str] = ["GET_ONE"] + HTTP_METHODS,
    custom_methods: Dict[str, Callable] = {},
    background_tasks_mapping: Dict[str, Callable] = {},
):
    if not create_model:
        create_model = pydantic_model
    response_models: Dict[str, Type] = {
        "get": List[pydantic_model],  # type: ignore
        "get_one": pydantic_model,
        "post": pydantic_model,
        "put": pydantic_model,
        "patch": pydantic_model,
        "delete": pydantic_model,
    }

    item_path = path_join(path, "{model_id}")
    paths: Dict[str, str] = {
        "get": path,
        "get_one": item_path,
        "post": path,
        "put": item_path,
        "patch": item_path,
        "delete": item_path,
    }

    async def get():
        return await orm_model.query.gino.all()

    async def get_one(model_id: int):
        item = await orm_model.get(model_id)
        if not item:
            raise HTTPException(
                status_code=404, detail=f"Object with id {model_id} does not exist!"
            )
        return item

    async def post(
        model: create_model, background_tasks: BackgroundTasks  # type: ignore
    ):
        try:
            obj = await orm_model.create(**model.dict())  # type: ignore
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
        ) as e:
            raise HTTPException(422, e.message)
        if background_tasks_mapping.get("post"):
            background_tasks.add_task(background_tasks_mapping["post"], obj)
        return obj

    async def put(model_id: int, model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        try:
            await item.update(**model.dict()).apply()  # type: ignore
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
        ) as e:
            raise HTTPException(422, e.message)
        return item

    async def patch(model_id: int, model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        try:
            await item.update(
                **model.dict(skip_defaults=True)  # type: ignore
            ).apply()
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError,
        ) as e:
            raise HTTPException(422, e.message)
        return item

    async def delete(model_id: int):
        item = await get_one(model_id)
        await item.delete()
        return item

    for method in allowed_methods:
        method_name = method.lower()
        router.add_api_route(  # type: ignore
            paths.get(method_name),
            custom_methods.get(method_name) or locals()[method_name],
            methods=[method_name if method in HTTP_METHODS else "get"],
            response_model=response_models.get(method_name),
        )


async def get_wallet_history(model, response):
    txes = (
        await BTC(
            settings.RPC_URL,
            xpub=model.xpub,
            rpc_user=settings.RPC_USER,
            rpc_pass=settings.RPC_PASS,
        ).history()
    )["transactions"]
    for i in txes:
        response.append({"date": i["date"], "txid": i["txid"], "amount": i["value"]})
