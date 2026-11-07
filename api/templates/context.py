import secrets
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from inspect import getattr_static
from typing import Any, cast

from dishka import AsyncContainer
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import inspect
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.types import TypeEngine

from api import models
from api.sqltypes import PydanticJSON
from api.templates import RenderResult, text_to_html

DECIMAL_KEY = "$decimal"
JSON_ADAPTER = TypeAdapter(Any)
COMPUTED_FIELD_TYPES = (property, cached_property, hybrid_property, AssociationProxy)


def _is_hidden(attr: ColumnProperty[Any]) -> bool:
    info = attr.info | getattr(attr.columns[0], "info", {})
    return models.HIDDEN_FROM_TEMPLATES.items() <= info.items()


def visible_fields(model_type: type[models.Model]) -> list[str]:
    mapper = inspect(model_type)
    columns = [attr.key for attr in mapper.column_attrs if not _is_hidden(attr)]
    relations = [
        relation.key for relation in mapper.relationships if models.EXPOSED_TO_TEMPLATES.items() <= relation.info.items()
    ]
    return [*columns, *relations]


def computed_fields(model_type: type[models.Model]) -> list[str]:
    return [
        name
        for name in dir(model_type)
        if not name.startswith("_")
        and name != "awaitable_attrs"
        and isinstance(getattr_static(model_type, name), COMPUTED_FIELD_TYPES)
    ]


@dataclass(frozen=True)
class ModelOverride:
    model: models.Model
    fields: Mapping[str, Any]


def with_fields(model: models.Model, **fields: Any) -> ModelOverride:
    return ModelOverride(model, fields)


class ContextBuilder:
    def __init__(self, *, html: bool = False) -> None:
        self.html = html
        self.nonce = secrets.token_hex(16)
        self.safe_key = f"$safe:{self.nonce}"
        self.targets: dict[str, models.RecordModel] = {}
        self.placeholders: dict[str, str] = {}
        self.has_fallback = False

    def build(self, context: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self._convert(value) for key, value in context.items()}

    def finish(self, text: str) -> RenderResult:
        if not self.placeholders:
            return RenderResult(text, self.html, self.has_fallback)
        converted = text_to_html(text)
        for placeholder, nested in self.placeholders.items():
            converted = converted.replace(placeholder, nested)
        return RenderResult(converted, True, self.has_fallback)

    def _convert_nested(self, nested: RenderResult) -> Any:
        self.has_fallback = self.has_fallback or nested.is_fallback
        if self.html:
            return {self.safe_key: nested.as_html().text}
        if not nested.is_html:
            return nested.text
        # A text parent's own text still has to be escaped, which can only happen after it is rendered.
        placeholder = f"BITCARTNESTED{self.nonce}N{len(self.placeholders)}X"
        self.placeholders[placeholder] = nested.text
        return placeholder

    def _convert(self, value: Any) -> Any:
        if isinstance(value, RenderResult):
            return self._convert_nested(value)
        if isinstance(value, ModelOverride):
            return {**self._convert_model(value.model), **{key: self._convert(item) for key, item in value.fields.items()}}
        if isinstance(value, models.Model):
            return self._convert_model(value)
        if isinstance(value, BaseModel):
            return {key: self._convert(getattr(value, key)) for key in type(value).model_fields}
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, Decimal):
            return {DECIMAL_KEY: format(value, "f")}
        if isinstance(value, datetime):
            return str(value)
        if isinstance(value, Mapping):
            return {str(key): self._convert(item) for key, item in value.items()}
        if isinstance(value, Iterable):
            return [self._convert(item) for item in value]
        return JSON_ADAPTER.dump_python(value, mode="json")

    def _convert_model(self, model: models.Model) -> dict[str, Any]:
        model_type = type(model)
        if model_type.template_blocked:
            raise TypeError(f"{model_type.__name__} can't be passed to a template, pass the fields it needs")
        unloaded = inspect(model).unloaded
        view = {key: self._convert(getattr(model, key)) for key in visible_fields(model_type) if key not in unloaded}
        for key in computed_fields(model_type):
            try:
                view[key] = self._convert(getattr(model, key))
            except InvalidRequestError:
                continue
        if isinstance(model, models.RecordModel):
            reference = f"{type(model).__name__}:{model.id}"
            self.targets[reference] = model
            view["_ref"] = reference
        return view


type TemplateOwner = models.Store | models.Product


@dataclass(frozen=True)
class TemplateTestData[OwnerT: TemplateOwner | None]:
    owner: OwnerT | None
    user: models.User
    container: AsyncContainer


type TemplateContextGetter[OwnerT: TemplateOwner | None] = Callable[[TemplateTestData[OwnerT]], Awaitable[Mapping[str, Any]]]


SAMPLE_VALUES: dict[type, Callable[[], Any]] = {
    Decimal: lambda: Decimal("10.50"),
    int: lambda: 1,
    float: lambda: 10.5,
    bool: lambda: False,
    datetime: models.utc_now,
    dict: dict,
    list: list,
}


def _sample_value(key: str, column_type: TypeEngine[Any]) -> Any:
    if isinstance(column_type, PydanticJSON):
        return column_type.pydantic_model()
    python_type = column_type.python_type
    if python_type is str:
        return f"sample {key}"
    if python_type not in SAMPLE_VALUES:
        raise TypeError(f"{key}: no sample value for {python_type.__name__}")
    return SAMPLE_VALUES[python_type]()


def _sample_graph(model_type: type[models.Model], instances: dict[type[models.Model], models.Model]) -> models.Model:
    if model_type in instances:
        return instances[model_type]
    mapper = inspect(model_type)
    instance = model_type(**{attr.key: _sample_value(attr.key, attr.columns[0].type) for attr in mapper.column_attrs})
    instances[model_type] = instance
    for relation in mapper.relationships:
        related = _sample_graph(relation.mapper.class_, instances)
        setattr(instance, relation.key, [related] if relation.uselist else related)
    return instance


def sample_model[ModelT: models.Model](model_type: type[ModelT]) -> ModelT:
    """Builds an unsaved model with every column and relation filled. Never link it to a saved object."""
    return cast(ModelT, _sample_graph(model_type, {}))


def describe_context(context: Mapping[str, Any]) -> str:
    parts = []
    for key, value in context.items():
        model = value.model if isinstance(value, ModelOverride) else value
        if isinstance(model, models.RecordModel):
            parts.append(f"{key}={type(model).__name__}({model.id})")
        else:
            parts.append(f"{key}: {type(value).__name__}")
    return ", ".join(parts)
