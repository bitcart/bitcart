import asyncio
import inspect
import secrets

from fastapi import HTTPException

from api.constants import ALPHABET, ID_LENGTH


def get_object_name(obj):
    return obj.__class__.__name__.lower()


def unique_id(length=ID_LENGTH):
    return "".join(secrets.choice(ALPHABET) for i in range(length))


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


def prepare_compliant_response(data):
    return {
        "count": len(data),
        "next": None,
        "previous": None,
        "result": data,
    }


def versiontuple(v):
    return tuple(map(int, v.split(".")))


def validate_list(v, allowed_values, error_text):
    if v not in allowed_values:
        message = ", ".join(map(str, allowed_values))
        raise HTTPException(422, f"{error_text} must be either of: {message}")
    return v
