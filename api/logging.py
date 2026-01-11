import logging
import re
import time
import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from logging.handlers import TimedRotatingFileHandler
from typing import Any, TypeVar, cast

import msgpack
import structlog
from opentelemetry import trace
from opentelemetry._logs import LoggerProvider, LogRecord, get_logger_provider
from opentelemetry.context import get_current
from opentelemetry.sdk._logs._internal import std_to_otel
from opentelemetry.semconv._incubating.attributes import code_attributes
from opentelemetry.semconv.attributes import exception_attributes
from structlog._log_levels import NAME_TO_LEVEL
from structlog.dev import plain_traceback

from api.constants import LOGSERVER_PORT
from api.schemas.base import Schema
from api.settings import Settings

RendererType = TypeVar("RendererType")

Logger = structlog.stdlib.BoundLogger

TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f %Z"

_EXCLUDE_ATTRS = {
    "exception",
    "exc_info",
    "timestamp",
    "event",
    "message",
    "lineno",
    "func_name",
    "pathname",
    "_record",
    "service.name",
    "trace_id",
    "span_id",
}


class StructlogOTELHandler:
    def __init__(self, logger_provider: LoggerProvider) -> None:
        self._logger_provider = logger_provider

    @staticmethod
    def _get_attributes(event_dict: structlog.typing.EventDict) -> dict[str, Any]:
        attributes = {k: v for k, v in event_dict.items() if k not in _EXCLUDE_ATTRS}
        attributes[code_attributes.CODE_FILE_PATH] = event_dict.get("pathname", "")
        attributes[code_attributes.CODE_FUNCTION_NAME] = event_dict.get("func_name", "")
        attributes[code_attributes.CODE_LINE_NUMBER] = event_dict.get("lineno", 0)
        if "exc_info" in event_dict:
            exctype, value, tb = event_dict["exc_info"]
            if exctype is not None:
                attributes[exception_attributes.EXCEPTION_TYPE] = exctype.__name__
            if value is not None and value.args:
                attributes[exception_attributes.EXCEPTION_MESSAGE] = str(value.args[0])
            if tb is not None:
                attributes[exception_attributes.EXCEPTION_STACKTRACE] = "".join(
                    traceback.format_exception(*event_dict["exc_info"])
                )
        return attributes

    @classmethod
    def _translate(cls, event_dict: structlog.typing.EventDict) -> dict[str, Any]:
        timestamp = int(datetime.strptime(event_dict["timestamp"], TIME_FORMAT).timestamp() * 1e9)
        observed_timestamp = time.time_ns()
        severity_number = std_to_otel(NAME_TO_LEVEL[event_dict["level"]])
        attributes = cls._get_attributes(event_dict)
        level_name = event_dict["level"]
        level_name = "WARN" if level_name == "WARNING" else level_name
        return {
            "timestamp": timestamp,
            "observed_timestamp": observed_timestamp,
            "context": get_current() or None,
            "severity_text": level_name,
            "severity_number": severity_number,
            "body": event_dict["event"],
            "attributes": attributes,
        }

    def __call__(
        self,
        logger: structlog.typing.WrappedLogger,
        name: str,
        event_dict: structlog.typing.EventDict,
    ) -> structlog.typing.EventDict:
        otel_logger = self._logger_provider.get_logger(event_dict["logger"])
        otel_logger.emit(LogRecord(**self._translate(event_dict)))
        return event_dict


class MsgpackHandler(logging.handlers.SocketHandler):
    def __init__(self, host: str, port: int) -> None:
        logging.handlers.SocketHandler.__init__(self, host, port)

    def msgpack_encoder(self, obj: Any) -> Any:
        if isinstance(obj, Schema):
            return obj.model_dump()
        if isinstance(obj, datetime):
            return {"__datetime__": True, "data": obj.strftime("%Y%m%dT%H:%M:%S.%f")}
        if isinstance(obj, Decimal):
            return {"__decimal__": True, "data": str(obj)}
        return str(obj)

    def makePickle(self, record: logging.LogRecord) -> bytes:
        if "_logger" in record.__dict__:  # added by structlog
            del record.__dict__["_logger"]
        return msgpack.packb(record.__dict__, default=self.msgpack_encoder)


class Logging[RendererType]:
    """Hubben logging configurator of `structlog` and `logging`.

    Customized implementation inspired by the following documentation:
    https://www.structlog.org/en/stable/standard-library.html#rendering-using-structlog-based-formatters-within-logging

    """

    timestamper = structlog.processors.TimeStamper(fmt=TIME_FORMAT, utc=False)

    @classmethod
    def get_level(cls, settings: Settings) -> str:
        return settings.LOG_LEVEL

    @classmethod
    def is_debug(cls, settings: Settings) -> bool:
        return settings.DEBUG

    @classmethod
    def debug_loggers(cls, settings: Settings) -> list[str]:
        if cls.is_debug(settings):
            return ["sqlalchemy.engine"]
        return []

    @classmethod
    def add_trace_context(cls, logger: Logger, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if "otelTraceID" in event_dict:
            event_dict["trace_id"] = event_dict.pop("otelTraceID")
        if "otelSpanID" in event_dict:
            event_dict["span_id"] = event_dict.pop("otelSpanID")
        if "otelServiceName" in event_dict:
            event_dict["service.name"] = event_dict.pop("otelServiceName")
        event_dict.pop("otelTraceSampled", None)
        if "trace_id" in event_dict and "span_id" in event_dict:
            return event_dict
        span = trace.get_current_span()
        if not span.is_recording():
            return event_dict
        ctx = span.get_span_context()
        if not ctx.is_valid:
            return event_dict
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
        tp = trace.get_tracer_provider()
        resource = getattr(tp, "resource", None)
        attrs = getattr(resource, "attributes", {}) if resource else {}
        svc = attrs.get("service.name")
        if svc:
            event_dict["service.name"] = svc
        return event_dict

    @classmethod
    def remove_callsite_params(
        cls,
        logger: Logger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict.pop("pathname", None)
        event_dict.pop("func_name", None)
        event_dict.pop("lineno", None)
        return event_dict

    @classmethod
    def get_common_processors(cls, *, settings: Settings) -> list[Any]:
        return [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.ExtraAdder(),
            cls.add_trace_context,
            cls.timestamper,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.PATHNAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            structlog.processors.format_exc_info,
            cls.remove_callsite_params,
        ]

    @classmethod
    def get_structlog_processors(cls, *, settings: Settings) -> list[Any]:
        return cls.get_common_processors(settings=settings) + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ]

    @classmethod
    def get_renderer(cls) -> RendererType:
        raise NotImplementedError()

    @classmethod
    def get_file_renderer(cls) -> RendererType:
        raise NotImplementedError()

    @classmethod
    def get_third_party_loggers(cls, settings: Settings) -> list[str]:
        loggers_list = ["asyncio"] + cls.debug_loggers(settings)
        loggers_list.append("uvicorn" if not settings.is_production() else "uvicorn.error")
        return loggers_list

    @classmethod
    def get_custom_level(cls, level: str, module: str) -> str | int:
        match module:
            case "asyncio":
                return logging.INFO
            case "uvicorn" | "uvicorn.error":
                return logging.INFO
            case _:
                return level

    @staticmethod
    def configure_third_party() -> None:
        logging.getLogger("sqlalchemy.engine.Engine").handlers = [logging.NullHandler()]
        logging.getLogger("python_multipart").setLevel(logging.CRITICAL + 1)
        logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL + 1)

    @classmethod
    def configure_stdlib(cls, *, settings: Settings, logserver: bool = False) -> None:
        cls.configure_third_party()
        level = cls.get_level(settings)
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=cls.get_common_processors(settings=settings),
            processors=[
                *((StructlogOTELHandler(get_logger_provider()),) if settings.OTEL_ENABLED else ()),
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                cast(structlog.typing.Processor, cls.get_renderer()),
            ],
        )
        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=cls.get_common_processors(settings=settings),
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                cast(structlog.typing.Processor, cls.get_file_renderer()),
            ],
        )
        console_handler = logging.StreamHandler()
        console_handler.set_name("default")
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        third_party_loggers = cls.get_third_party_loggers(settings)
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            is_enabled = logger_name in third_party_loggers
            is_third_party_child = any(logger_name.startswith(parent + ".") for parent in third_party_loggers)
            if is_enabled or is_third_party_child:
                logger.setLevel(cls.get_custom_level(level, logger_name) if is_enabled else logging.NOTSET)
                logger.handlers.clear()
                logger.propagate = True
                if logger_name.startswith("uvicorn") or logger_name.startswith("sqlalchemy.engine"):  # for better DX
                    logger.addHandler(console_handler)
                    logger.propagate = False
            else:
                logger.disabled = True
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(level)
        root_logger.propagate = False
        if logserver:
            root_logger.addHandler(console_handler)
            file_handler = cls.configure_file_logging(settings=settings, formatter=file_formatter, level=level)
            if file_handler is not None:
                root_logger.addHandler(file_handler)
        else:
            handler = MsgpackHandler(settings.logserver_client_host, LOGSERVER_PORT)
            handler.setLevel(level)
            root_logger.addHandler(handler)

    @classmethod
    def configure_structlog(cls, *, settings: Settings) -> None:
        structlog.configure_once(
            processors=cls.get_structlog_processors(settings=settings),
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    @classmethod
    def configure(cls, *, settings: Settings, logserver: bool = False) -> None:
        cls.configure_stdlib(settings=settings, logserver=logserver)
        cls.configure_structlog(settings=settings)

    @staticmethod
    def timed_log_namer(default_name: str) -> str:
        base_filename, *ext, date = default_name.split(".")
        return f"{base_filename}{date}.{'.'.join(ext)}"  # i.e. "bitcart12345678.log"

    @classmethod
    def configure_file_logging(
        cls, *, level: str, formatter: logging.Formatter, settings: Settings
    ) -> TimedRotatingFileHandler | None:
        if settings.log_file:
            handler = TimedRotatingFileHandler(settings.log_file, when="midnight")
            handler.suffix = "%Y%m%d"
            handler.extMatch = re.compile(r"^\d{8}(\.\w+)?$")
            handler.namer = cls.timed_log_namer
            handler.setFormatter(formatter)
            handler.setLevel(level)
            return handler
        return None


class Development(Logging[structlog.dev.ConsoleRenderer]):
    @classmethod
    def get_renderer(cls) -> structlog.dev.ConsoleRenderer:
        return structlog.dev.ConsoleRenderer(colors=True, exception_formatter=plain_traceback, pad_level=False)

    @classmethod
    def get_file_renderer(cls) -> structlog.dev.ConsoleRenderer:
        return structlog.dev.ConsoleRenderer(colors=False, exception_formatter=plain_traceback, pad_level=False)


# TODO: implement it one day

# class Production(Logging[structlog.processors.JSONRenderer]):
#     @classmethod
#     def get_renderer(cls) -> structlog.processors.JSONRenderer:
#         return structlog.processors.JSONRenderer()

#     @classmethod
#     def get_file_renderer(cls) -> structlog.processors.JSONRenderer:
#         return structlog.processors.JSONRenderer()

Production = Development


def configure(*, settings: Settings, logserver: bool = False) -> None:
    if settings.is_testing() or settings.is_development():
        Development.configure(settings=settings, logserver=logserver)
    else:
        Production.configure(settings=settings, logserver=logserver)


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def get_exception_message(exc: Exception) -> str:
    return "\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


@contextmanager
def log_errors(logger: Logger) -> Iterator[None]:  # pragma: no cover
    try:
        yield
    except Exception as e:
        logger.error(get_exception_message(e))


def get_logger(name: str) -> Logger:
    logger: Logger = structlog.get_logger(name)
    return logger
