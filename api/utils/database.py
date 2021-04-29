from contextlib import contextmanager

import asyncpg
from fastapi import HTTPException

from api import models


@contextmanager
def safe_db_write():
    try:
        yield
    except asyncpg.exceptions.IntegrityConstraintViolationError as e:
        raise HTTPException(422, str(e))


async def get_object(model, model_id, user=None):
    query = model.query.where(model.id == model_id)
    if model != models.User and user:
        query = query.where(model.user_id == user.id)
    data = await query.gino.first()
    if not data:
        raise HTTPException(404, f"{model.__name__} with id {model_id} does not exist!")
    return data
