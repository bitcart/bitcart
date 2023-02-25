from contextlib import asynccontextmanager, contextmanager
from typing import Type, TypeVar

import asyncpg
from fastapi import HTTPException
from sqlalchemy import distinct

from api import db, models
from api.logger import get_exception_message, get_logger
from api.plugins import apply_filters, run_hook

logger = get_logger(__name__)

ModelType = TypeVar("ModelType")


@contextmanager
def safe_db_write():
    try:
        yield
    except asyncpg.exceptions.IntegrityConstraintViolationError as e:  # pragma: no cover
        raise HTTPException(422, str(e))


def get_kwargs(model, data, additional_kwargs, user=None):
    kwargs = data if isinstance(data, dict) else data.dict()
    kwargs.update(additional_kwargs)
    if user:
        kwargs["user_id"] = user.id
    return model.process_kwargs(kwargs)


def prepare_create_kwargs(model, data, user=None, **additional_kwargs):
    kwargs = get_kwargs(model, data, additional_kwargs, user)
    kwargs = model.prepare_create(kwargs)
    return kwargs


async def create_object_core(model, kwargs):
    model = model(**kwargs)  # Create object instance to allow calling instance methods
    await model.validate(kwargs)
    with safe_db_write():
        result = await model.create(**kwargs)
    return await apply_filters(f"db_create_{model.__class__.__name__.lower()}", result)


async def create_object(model: Type[ModelType], data, user=None, **additional_kwargs) -> ModelType:
    kwargs = prepare_create_kwargs(model, data, user, **additional_kwargs)
    return await create_object_core(model, kwargs)


async def modify_object(model, data, **additional_kwargs):
    kwargs = get_kwargs(model, data, additional_kwargs)
    kwargs = model.prepare_edit(kwargs)
    await model.validate(kwargs)
    with safe_db_write():
        try:
            await model.update(**kwargs).apply()
            await run_hook(f"db_modify_{model.__class__.__name__.lower()}", model)
        except asyncpg.exceptions.PostgresSyntaxError as e:  # pragma: no cover
            logger.error(get_exception_message(e))


async def get_object(
    model: Type[ModelType],
    model_id=None,
    user=None,
    custom_query=None,
    raise_exception=True,
    load_data=True,
    user_id=None,
    atomic_update=False,
) -> ModelType:
    if user_id is None and user is not None:
        user_id = user.id
    if custom_query is not None:
        query = custom_query
    else:
        query = model.query.where(model.id == model_id)
        if model != models.User and user_id:
            query = query.where(model.user_id == user_id)
    if atomic_update:
        query = query.with_for_update()
    item = await query.gino.first()
    if not item:
        if raise_exception:
            raise HTTPException(404, f"{model.__name__} with id {model_id} does not exist!")
        return
    if load_data:
        await item.load_data()
    return item


async def get_scalar(query, func, column, use_distinct=True):
    column = distinct(column) if use_distinct else column
    return await query.with_only_columns([func(column)]).order_by(None).gino.scalar() or 0


async def postprocess_func(items):
    for item in items:
        await item.load_data()
    return items


async def paginate_object(model, pagination, user, *args, **kwargs):
    return await pagination.paginate(model, user.id if user else None, postprocess=postprocess_func, *args, **kwargs)


@asynccontextmanager
async def iterate_helper():
    async with db.db.acquire() as conn:
        async with conn.transaction():
            yield


async def get_objects(model, ids, postprocess=True):  # TODO: maybe use iterate instead?
    data = await model.query.where(model.id.in_(ids)).gino.all()
    if postprocess:
        await postprocess_func(data)
    return data
