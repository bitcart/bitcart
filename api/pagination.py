# pylint: disable=no-member
import asyncio
from typing import TYPE_CHECKING, Callable, Optional, Union

from fastapi import Query
from sqlalchemy import Text, and_, or_, select, text
from sqlalchemy.sql import select as sql_select, join
from starlette.requests import Request
import asyncpg

from .db import db
from . import models

if TYPE_CHECKING:
    from gino.declarative import ModelType  # pragma: no cover


class Pagination:
    default_offset = 0
    default_limit = 5
    max_offset = None
    max_limit = 1000

    def __init__(
        self,
        request: Request,
        offset: int = Query(default=default_offset, ge=0, le=max_offset),
        limit: int = Query(default=default_limit, ge=-1, le=max_limit),
        query: str = Query(default=""),
        sort: str = Query(default=""),
        desc: bool = Query(default=True),
    ):
        self.request = request
        self.offset = offset
        self.limit = limit
        self.query = query
        self.sort = sort
        self.desc = desc
        self.desc_s = "desc" if desc else ""
        self.model: Optional["ModelType"] = None

    async def get_count(self, query) -> int:
        query = query.with_only_columns(
            [db.func.count(self.model.id)]  # type: ignore
        ).order_by(None)

        return await query.gino.scalar()

    def get_next_url(self, count) -> Union[None, str]:
        if self.offset + self.limit >= count or self.limit == -1:
            return None
        return str(
            self.request.url.include_query_params(
                limit=self.limit, offset=self.offset + self.limit
            )
        )

    def get_previous_url(self) -> Union[None, str]:
        if self.offset <= 0:
            return None

        if self.offset - self.limit <= 0:
            return str(self.request.url.remove_query_params(keys=["offset"]))

        return str(
            self.request.url.include_query_params(
                limit=self.limit, offset=self.offset - self.limit
            )
        )

    async def get_list(self, query) -> list:
        if self.limit != -1:
            query = query.limit(self.limit)
        if self.sort:
            query = query.order_by(text(f"{self.sort} {self.desc_s}"))
        try:
            return await query.offset(self.offset).gino.all()
        except asyncpg.exceptions.UndefinedColumnError:
            return []

    def search(self, models):
        if not self.query:
            return []
        return or_(
            *[
                getattr(model, m.key).cast(Text).ilike(f"%{self.query}%")
                for model in models
                for m in model.__table__.columns
            ]
        )

    async def paginate(self, model, postprocess: Optional[Callable] = None) -> dict:
        self.model = model
        select_from = model
        models_l = [model]
        for field in self.model.__table__.c:
            if field.key.endswith("_id"):
                modelx = getattr(models, field.key[:-3].capitalize())
                select_from = select_from.join(modelx)
                models_l.append(modelx)
        query = model.query.select_from(select_from)
        queries = self.search(models_l)
        if queries != []:
            query = query.where(queries)
        count, data = await asyncio.gather(self.get_count(query), self.get_list(query))
        if postprocess:
            data = await postprocess(data)
        return {
            "count": count,
            "next": self.get_next_url(count),
            "previous": self.get_previous_url(),
            "result": data,
        }
