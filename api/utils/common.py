import asyncio
import inspect
import json
import secrets
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from aiohttp import ClientSession
from anyio import Semaphore
from dateutil.parser import isoparse
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from api import utils
from api.constants import ALPHABET, ID_LENGTH, STR_TO_BOOL_MAPPING, TOTP_ALPHABET, TOTP_LENGTH


def get_object_name(obj):
    return obj.__class__.__name__.lower()


def unique_id(length=ID_LENGTH):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def unique_verify_code(length=TOTP_LENGTH):
    return "".join(secrets.choice(TOTP_ALPHABET) for _ in range(length))


async def run_universal(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):  # pragma: no cover
        result = await result
    return result


async def run_repeated(func, interval, initial_delay=None):  # pragma: no cover
    if initial_delay is None:
        initial_delay = interval
    first_iter = True
    while True:
        await asyncio.sleep(initial_delay if first_iter else interval)
        await run_universal(func)
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


def is_int(v):
    try:
        int(v)
        return True
    except ValueError:
        return False


class SearchQuery:
    DATE_FORMATS = {"h": "hours", "d": "days", "w": "weeks", "m": 30, "y": 30 * 12}

    def __init__(self, query):
        self.query = query
        self.text = []
        self.filters = defaultdict(list)
        for item in query.split():
            parts = item.split(":")
            is_quoted = item[0] == '"' and item[-1] == '"'
            if len(parts) >= 2 and not is_quoted:
                key = parts[0].lower()
                self.filters[key].append(":".join(parts[1:]))
            else:
                if is_quoted:
                    item = item[1:-1]
                self.text.append(item)
        self.text = " ".join(self.text)

    def parse_datetime(self, key):
        if key not in self.filters:
            return
        now = utils.time.now()
        date = self.filters.pop(key)[0]
        if len(date) >= 3 and date[0] == "-" and date[-1] in self.DATE_FORMATS and is_int(date[1:-1]):
            val = int(date[1:-1])
            dt_format = date[-1]
            if dt_format in ("m", "y"):
                key = "days"
                val *= self.DATE_FORMATS[dt_format]
            else:
                key = self.DATE_FORMATS[dt_format]
            return now - timedelta(**{key: val})
        try:
            return isoparse(date)
        except ValueError:
            return

    def get_created_filter(self, model, key="created"):
        if getattr(model, key, None) is None:  # pragma: no cover
            return []
        self.filters.pop(key, None)
        start_date = self.parse_datetime("start_date")
        end_date = self.parse_datetime("end_date")
        queries = []
        if start_date:
            queries.append(model.created >= start_date)
        if end_date:
            queries.append(model.created <= end_date)
        return queries

    def __bool__(self):
        return bool(self.text or self.filters)


def str_to_bool(s):
    s = s.lower()

    if s in STR_TO_BOOL_MAPPING:
        return STR_TO_BOOL_MAPPING[s]
    return False


def prepare_query_params(request, custom_params=()):
    params = dict(request.query_params)
    # TODO: make it better, for now must be kept in sync with pagination.py
    for key in ("model", "offset", "limit", "query", "multiple", "sort", "desc") + custom_params:
        params.pop(key, None)
    return params


# To not have too many threads running (which could happen on too many concurrent
# requests, we limit it with a semaphore.
MAX_CONCURRENT_THREADS = 50
MAX_THREADS_GUARD = Semaphore(MAX_CONCURRENT_THREADS)


async def run_async(func, *args, **kwargs):  # pragma: no cover
    async with MAX_THREADS_GUARD:
        return await run_in_threadpool(func, *args, **kwargs)


def precise_decimal(v):  # pragma: no cover
    return Decimal(str(v))


async def send_request(method, url, *args, return_json=True, **kwargs):  # pragma: no cover
    async with ClientSession() as session, session.request(method, url, *args, **kwargs) as resp:
        if return_json:
            return await resp.json()
        return resp, await resp.text()


class DecimalAwareJSONEncoder(json.JSONEncoder):  # pragma: no cover
    def default(self, obj):
        if isinstance(obj, Decimal):
            return {"__type__": "Decimal", "value": str(obj)}
        return super().default(obj)


def decimal_aware_object_hook(obj):  # pragma: no cover
    if isinstance(obj, dict) and obj.get("__type__") == "Decimal":
        return Decimal(obj["value"])
    return obj
