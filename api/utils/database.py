from numbers import Number
from typing import Any, cast

from advanced_alchemy.base import ModelProtocol
from sqlalchemy import Select, distinct
from sqlalchemy.orm import InstrumentedAttribute

from api.db import AsyncSession


async def get_scalar[ModelType: ModelProtocol](
    session: AsyncSession,
    query: Select[tuple[ModelType]],
    db_func: Any,
    column: InstrumentedAttribute[Any],
    use_distinct: bool = True,
) -> Number:
    query_column = distinct(column) if use_distinct else column
    return cast(
        Number,
        (await session.execute(query.with_only_columns(db_func(query_column)).order_by(None))).scalar_one() or 0,
    )
