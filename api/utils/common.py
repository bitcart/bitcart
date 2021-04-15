import asyncio
import inspect
import secrets

from api.constants import ALPHABET


def get_object_name(obj):
    return obj.__class__.__name__.lower()


def unique_id(length=32):
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
