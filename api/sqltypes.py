from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.types import TypeDecorator, TypeEngine

from api.schemas.base import Schema


class PydanticJSON(TypeDecorator[Schema]):
    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_model: type[Schema], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._model = pydantic_model

    def process_bind_param(self, value: Any, dialect: Any) -> dict[str, Any] | None:
        if isinstance(value, Schema):
            return value.model_dump()
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Schema | None:
        if value is None:
            return None
        raw = value or {}
        return self._model.model_validate(raw)


def MutableModel(pydantic_model: type[Schema]) -> TypeEngine[Schema]:
    class MutableModel(Mutable, pydantic_model):  # type: ignore[valid-type, misc]
        @classmethod
        def coerce(cls, key: str, value: Any) -> "MutableModel | None":
            if not isinstance(value, cls):
                if isinstance(value, pydantic_model):
                    return cls(**value.model_dump())
                if isinstance(value, dict):
                    return cls(**value)
                return Mutable.coerce(key, value)
            return value

        def __setattr__(self, key: str, value: Any) -> None:
            super().__setattr__(key, value)
            self.changed()

    return MutableModel.as_mutable(PydanticJSON(pydantic_model))
