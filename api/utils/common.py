import asyncio
import inspect
import json
import secrets
from collections import defaultdict
from collections.abc import Callable, Sized
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast, overload

from advanced_alchemy.base import ModelProtocol
from aiohttp import ClientResponse, ClientSession
from dateutil.parser import isoparse
from dishka import AsyncContainer, Scope
from fastapi import HTTPException
from pydantic import create_model
from pydantic.fields import FieldInfo
from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute
from ulid import ULID

from api import utils
from api.constants import STR_TO_BOOL_MAPPING, TOTP_ALPHABET, TOTP_LENGTH
from api.logging import Logger, log_errors
from api.schemas.base import Schema


def get_object_name(obj: object) -> str:
    return obj.__class__.__name__.lower()


def unique_id() -> str:
    return str(ULID())


def unique_verify_code(length: int = TOTP_LENGTH) -> str:
    return "".join(secrets.choice(TOTP_ALPHABET) for _ in range(length))


def to_optional[T: Schema](model: type[T]) -> type[T]:
    optional_fields: Any = {}
    for field_name, model_field in model.model_fields.items():
        if model_field.default_factory is not None or model_field.validate_default:
            optional_fields[field_name] = (model_field.annotation, model_field)
        else:
            new_field_info = FieldInfo.merge_field_infos(model_field, FieldInfo(default=None))
            optional_fields[field_name] = (model_field.annotation, new_field_info)
    return create_model(f"Optional{model.__name__}", __base__=model, **optional_fields)


def get_sqla_attr(
    model: ModelProtocol,
    key: str,
) -> InstrumentedAttribute[Any]:
    return cast("InstrumentedAttribute[Any]", getattr(model, key))


def prepare_compliant_response(data: Sized) -> dict[str, Any]:
    return {
        "count": len(data),
        "next": None,
        "previous": None,
        "result": data,
    }


def versiontuple(v: str) -> tuple[int, ...]:
    return tuple(map(int, v.split(".")))


def validate_list(v: Any, allowed_values: list[Any], error_text: str) -> Any:
    if v not in allowed_values:
        message = ", ".join(map(str, allowed_values))
        raise HTTPException(422, f"{error_text} must be either of: {message}")
    return v


def str_to_bool(s: str) -> bool:
    s = s.lower()

    if s in STR_TO_BOOL_MAPPING:
        return STR_TO_BOOL_MAPPING[s]
    return False


@overload
async def send_request(method: str, url: str, *args: Any, return_json: Literal[True] = True, **kwargs: Any) -> Any: ...
@overload
async def send_request(
    method: str, url: str, *args: Any, return_json: Literal[False], **kwargs: Any
) -> tuple[ClientResponse, str]: ...
@overload
async def send_request(
    method: str, url: str, *args: Any, return_json: bool, **kwargs: Any
) -> Any | tuple[ClientResponse, str]: ...
async def send_request(method: str, url: str, *args: Any, return_json: bool = True, **kwargs: Any) -> Any:
    async with ClientSession() as session, session.request(method, url, *args, **kwargs) as resp:
        if return_json:
            return await resp.json()
        return resp, await resp.text()


def precise_decimal(v: Any) -> Decimal:  # pragma: no cover
    return Decimal(str(v))


class DecimalAwareJSONEncoder(json.JSONEncoder):  # pragma: no cover
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return {"__type__": "Decimal", "value": str(obj)}
        return super().default(obj)


def decimal_aware_object_hook(obj: Any) -> Any:  # pragma: no cover
    if isinstance(obj, dict) and obj.get("__type__") == "Decimal":
        return Decimal(obj["value"])
    return obj


async def run_universal(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):  # pragma: no cover
        result = await result
    return result


async def run_repeated(func: Callable[..., Any], interval: int, initial_delay: int | None = None) -> None:  # pragma: no cover
    if initial_delay is None:
        initial_delay = interval
    first_iter = True
    while True:
        await asyncio.sleep(initial_delay if first_iter else interval)
        await run_universal(func)
        first_iter = False


async def concurrent_safe_run(
    func: Callable[..., Any], *args: Any, container: AsyncContainer, logger: Logger, **kwargs: Any
) -> None:  # pragma: no cover
    async with container(scope=Scope.REQUEST) as request_container:
        with log_errors(logger):
            await run_universal(func, *args, di_context=request_container, **kwargs)


def is_int(v: Any) -> bool:
    try:
        int(v)
        return True
    except ValueError:
        return False


class SearchQuery:
    DATE_FORMATS = {"h": "hours", "d": "days", "w": "weeks", "m": 30, "y": 30 * 12}

    def __init__(self, query: str) -> None:
        self.query = query
        text = []
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
                text.append(item)
        self.text = " ".join(text)

    def parse_datetime(self, key: str) -> datetime | None:
        if key not in self.filters:
            return None
        now = utils.time.now()
        date = self.filters.pop(key)[0]
        if len(date) >= 3 and date[0] == "-" and date[-1] in self.DATE_FORMATS and is_int(date[1:-1]):
            val = int(date[1:-1])
            dt_format = date[-1]
            if dt_format in ("m", "y"):
                key = "days"
                val *= cast(int, self.DATE_FORMATS[dt_format])
            else:
                key = cast(str, self.DATE_FORMATS[dt_format])
            return now - timedelta(**{key: val})
        try:
            return isoparse(date)
        except ValueError:
            return None

    def get_created_filter(self, model: type[ModelProtocol], key: str = "created") -> list[ColumnElement[bool]]:
        if getattr(model, key, None) is None:  # pragma: no cover
            return []
        self.filters.pop(key, None)
        start_date = self.parse_datetime("start_date")
        end_date = self.parse_datetime("end_date")
        queries = []
        if start_date:
            queries.append(get_sqla_attr(cast(ModelProtocol, model), "created") >= start_date)
        if end_date:
            queries.append(get_sqla_attr(cast(ModelProtocol, model), "created") <= end_date)
        return queries

    def __bool__(self) -> bool:
        return bool(self.text or self.filters)
