from contextlib import contextmanager

import asyncpg
from fastapi import HTTPException


@contextmanager
def safe_db_write():
    try:
        yield
    except asyncpg.exceptions.IntegrityConstraintViolationError as e:
        raise HTTPException(422, e.message)
