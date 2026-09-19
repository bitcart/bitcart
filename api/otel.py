import os

from opentelemetry.instrumentation import auto_instrumentation

from api.version import VERSION

# asyncpg spans duplicate the ones sqlalchemy instrumentation emits,
# structlog records are exported by api.logging.StructlogOTELProcessor instead
DISABLED_INSTRUMENTATIONS = ["asyncpg", "structlog"]


def append_resource_attributes() -> None:
    resource_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    version_attr = f"service.version={VERSION}"
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{resource_attrs},{version_attr}" if resource_attrs else version_attr


def disable_instrumentations() -> None:
    disabled = [name for name in os.environ.get("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "").split(",") if name]
    disabled.extend(name for name in DISABLED_INSTRUMENTATIONS if name not in disabled)
    os.environ["OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"] = ",".join(disabled)


def initialize() -> None:
    append_resource_attributes()
    disable_instrumentations()
    auto_instrumentation.initialize()
