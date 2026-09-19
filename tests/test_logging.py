import logging
import time
from collections.abc import Iterator, Mapping

import pytest
import structlog
from opentelemetry import trace
from opentelemetry._logs import LogRecord, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util.types import AnyValue

from api.logging import Logger, get_logger
from api.logging import configure as configure_logging
from api.settings import Settings


@pytest.fixture(scope="session")
def otel_exporter() -> InMemoryLogRecordExporter:
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    set_logger_provider(provider)
    trace.set_tracer_provider(TracerProvider())
    return exporter


@pytest.fixture
def exported(settings: Settings, otel_exporter: InMemoryLogRecordExporter) -> Iterator[InMemoryLogRecordExporter]:
    otel_exporter.clear()
    structlog.reset_defaults()
    configure_logging(settings=settings.model_copy(update={"OTEL_ENABLED": True}))
    yield otel_exporter
    structlog.reset_defaults()
    configure_logging(settings=settings)


@pytest.fixture
def logger(request: pytest.FixtureRequest, exported: InMemoryLogRecordExporter) -> Logger:
    return get_logger(f"tests.{request.node.name}")


def only_record(exported: InMemoryLogRecordExporter) -> LogRecord:
    records = exported.get_finished_logs()
    assert len(records) == 1
    return records[0].log_record


def only_scope(exported: InMemoryLogRecordExporter) -> str:
    records = exported.get_finished_logs()
    assert len(records) == 1
    scope = records[0].instrumentation_scope
    assert scope is not None
    return scope.name


def only_attributes(exported: InMemoryLogRecordExporter) -> Mapping[str, AnyValue]:
    attributes = only_record(exported).attributes
    assert attributes is not None
    return attributes


def test_structlog_record_is_exported_once(exported: InMemoryLogRecordExporter, logger: Logger) -> None:
    logger.info("hello", invoice_id="INV-1")
    assert only_attributes(exported)["invoice_id"] == "INV-1"


def test_stdlib_record_is_exported_once(exported: InMemoryLogRecordExporter) -> None:
    logging.getLogger("uvicorn.error").info("hello")
    assert only_record(exported).body == "hello"


def test_stdlib_record_goes_through_structlog(exported: InMemoryLogRecordExporter) -> None:
    structlog.contextvars.bind_contextvars(correlation_id="abc-123")
    logging.getLogger("uvicorn.error").info("hello")
    structlog.contextvars.clear_contextvars()
    attributes = only_attributes(exported)
    assert attributes["logger"] == "uvicorn.error"
    assert attributes["correlation_id"] == "abc-123"


def test_scope_is_the_logger_name(exported: InMemoryLogRecordExporter) -> None:
    logging.getLogger("uvicorn.error").info("hello")
    assert only_scope(exported) == "uvicorn.error"


def test_trace_id_is_set_on_the_record(exported: InMemoryLogRecordExporter, logger: Logger) -> None:
    with trace.get_tracer("test").start_as_current_span("work") as span:
        logger.info("hello")
    assert only_record(exported).trace_id == span.get_span_context().trace_id


def test_service_name_is_not_an_attribute(exported: InMemoryLogRecordExporter, logger: Logger) -> None:
    with trace.get_tracer("test").start_as_current_span("work"):
        logger.info("hello")
    assert "service.name" not in only_attributes(exported)


def test_exception_is_exported(exported: InMemoryLogRecordExporter, logger: Logger) -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")
    assert "ValueError: boom" in str(only_attributes(exported)["exception.stacktrace"])


@pytest.fixture
def named_timezone(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_timestamp_is_event_time(exported: InMemoryLogRecordExporter, logger: Logger, named_timezone: None) -> None:
    logger.info("hello")
    record = only_record(exported)
    assert record.timestamp is not None
    assert record.observed_timestamp - record.timestamp < 1_000_000_000
