import contextlib
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

DecimalAsFloat = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


def iter_attributes(
    obj: Any,
) -> Iterator[tuple[str, Any]]:  # to do the from_attributes job because pydantic doesn't do it before validator
    for k in dir(obj):
        if not k.startswith("_") and k not in (
            "model_fields",
            "model_computed_fields",
        ):  # pydantic deprecated access on the instance
            with contextlib.suppress(Exception):
                v = getattr(obj, k)
                if not callable(v):
                    yield k, v


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="wrap")
    @classmethod
    def ensure_dict(cls, values: Any, handler: Any) -> Any:
        if not isinstance(values, dict):
            values = dict(iter_attributes(values))
        values = {k: cls._prepare_value(v) for k, v in values.items()}
        return handler(values)

    @staticmethod
    def _prepare_value(v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class MetadataInput(Schema):
    metadata: dict[str, Any] = Field(
        description="Metadata associated with the object.",
        default_factory=dict,
        serialization_alias="meta",
        validation_alias="metadata",
    )


class MetadataOutput(Schema):
    metadata: dict[str, Any] = Field(
        description="Metadata associated with the object.",
        default_factory=dict,
        serialization_alias="metadata",
        validation_alias="meta",
    )


class TimestampedSchema(Schema):
    created: datetime = Field(description="Creation timestamp of the object.")
    updated: datetime | None = Field(description="Last modification timestamp of the object.")
