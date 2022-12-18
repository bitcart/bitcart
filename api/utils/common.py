import asyncio
import inspect
import secrets
from collections import defaultdict
from datetime import timedelta

from dateutil.parser import isoparse
from fastapi import HTTPException

from api import utils
from api.constants import ALPHABET, ID_LENGTH, STR_TO_BOOL_MAPPING


def get_object_name(obj):
    return obj.__class__.__name__.lower()


def unique_id(length=ID_LENGTH):
    return "".join(secrets.choice(ALPHABET) for i in range(length))


async def run_universal(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):  # pragma: no cover
        result = await result
    return result


async def run_repeated(func, timeout, start_timeout=None):  # pragma: no cover
    if not start_timeout:
        start_timeout = timeout
    first_iter = True
    while True:
        await asyncio.sleep(start_timeout if first_iter else timeout)
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
