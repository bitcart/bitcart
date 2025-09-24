from typing import Any

from advanced_alchemy.base import ModelProtocol
from advanced_alchemy.repository import LoadSpec, SQLAlchemyAsyncRepository

from api.db import AsyncSession


class CRUDRepository[ModelType: ModelProtocol](SQLAlchemyAsyncRepository[ModelType]):
    LOAD_OPTIONS: LoadSpec | None = None
    merge_loader_options = False

    def __init__(self, session: AsyncSession, *args: Any, **kwargs: Any) -> None:
        kwargs["wrap_exceptions"] = False
        kwargs["uniquify"] = True
        kwargs["load"] = kwargs.get("load", self.LOAD_OPTIONS)
        super().__init__(*args, session=session, **kwargs)
