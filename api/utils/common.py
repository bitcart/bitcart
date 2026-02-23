import asyncio
import inspect
import json
import secrets
import traceback
from collections import defaultdict
from collections.abc import Callable, Sized
from datetime import datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Annotated, Any, Literal, cast, overload

from advanced_alchemy.base import ModelProtocol
from aiohttp import ClientResponse, ClientSession
from dishka import AsyncContainer, Scope
from fastapi import HTTPException
from pydantic import Field, create_model
from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute
from ulid import ULID

from api import utils
from api.constants import STR_TO_BOOL_MAPPING, TFA_RECOVERY_ALPHABET
from api.logging import Logger, get_exception_message, log_errors
from api.schemas.base import Schema


def get_object_name(obj: object) -> str:
    return obj.__class__.__name__.lower()


def unique_id() -> str:
    return str(ULID())


def generate_hyphenated_code(part_length: int, *, upper: bool = False) -> str:
    part1 = "".join(secrets.choice(TFA_RECOVERY_ALPHABET) for _ in range(part_length))
    part2 = "".join(secrets.choice(TFA_RECOVERY_ALPHABET) for _ in range(part_length))
    code = f"{part1}-{part2}"
    return code.upper() if upper else code


# NOTE: when https://github.com/pydantic/pydantic/issues/1673 is fixed, this can be removed
def to_optional[T: Schema](model: type[T]) -> type[T]:
    optional_fields: Any = {}
    for field_name, field_info in model.model_fields.items():
        field_dict = field_info.asdict()
        if not field_info.is_required():
            optional_fields[field_name] = (field_info.annotation, field_info)
        else:
            optional_fields[field_name] = (
                Annotated[field_dict["annotation"] | None, *field_dict["metadata"], Field(**field_dict["attributes"])],  # noqa: F821
                None,
            )
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
        self.metadata_filters = defaultdict(list)
        for item in query.split():
            parts = item.split(":")
            is_quoted = item[0] == '"' and item[-1] == '"'
            if len(parts) >= 2 and not is_quoted:
                key = parts[0].lower()
                value = ":".join(parts[1:])
                if key.startswith("metadata."):
                    field_name = key[9:]
                    self.metadata_filters[field_name].append(value)
                else:
                    self.filters[key].append(value)
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
            return datetime.fromisoformat(date)
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
        return bool(self.text or self.filters or self.metadata_filters)


def excepthook_handler(
    logger: Logger,
    excepthook: Callable[[type[BaseException], BaseException, TracebackType | None], Any],
) -> Callable[[type[BaseException], BaseException, TracebackType | None], Any]:
    def internal_error_handler(type_: type[BaseException], value: BaseException, tb: TracebackType | None) -> Any:
        if type_ is not KeyboardInterrupt:
            logger.error("\n" + "".join(traceback.format_exception(type_, value, tb)))
        return excepthook(type_, value, tb)

    return internal_error_handler


def handle_event_loop_exception(logger: Logger, loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    msg = get_exception_message(context["exception"]) if "exception" in context else context["message"]
    logger.error(msg)
