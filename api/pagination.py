# pylint: disable=no-member
import asyncio
from typing import TYPE_CHECKING, Callable, Optional, Union

import asyncpg
from fastapi import Query
from sqlalchemy import Text, and_, distinct, func, or_, select, text
from sqlalchemy.sql import join
from sqlalchemy.sql import select as sql_select
from starlette.requests import Request

from . import models, utils
from .db import db

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
        multiple: bool = Query(default=False),
        sort: str = Query(default=""),
        desc: bool = Query(default=True),
    ):
        self.request = request
        self.offset = offset
        self.limit = limit
        self.query = query
        self.multiple = multiple
        if self.multiple:
            self.query = self.query.replace(",", "|")
        self.sort = sort
        self.desc = desc
        self.desc_s = "desc" if desc else ""
        self.model: Optional["ModelType"] = None

    async def get_count(self, query) -> int:
        query = query.with_only_columns(
            [db.func.count(distinct(self.model.id))]  # type: ignore
        ).order_by(None)

        return await query.gino.scalar() or 0

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
                getattr(model, m.key)
                .cast(Text)
                .op("~*")(
                    f"{self.query}"
                )  # NOTE: not cross-db, postgres case-insensitive regex
                for model in models
                for m in model.__table__.columns
            ]
        )

    async def paginate(
        self,
        model,
        data_source,
        user_id=None,
        store_id=None,
        category=None,
        min_price=None,
        max_price=None,
        sale=False,
        postprocess: Optional[Callable] = None,
    ) -> dict:
        self.model = model
        if model == models.Product and sale:
            query = (
                model.query.select_from(
                    data_source.join(models.DiscountxProduct).join(models.Discount)
                )
                .having(func.count(models.DiscountxProduct.product_id) > 0)
                .where(models.Discount.end_date > utils.now())
            )
        else:
            query = model.query.select_from(data_source)
        models_l = [model]
        if model != models.User:
            for field in self.model.__table__.c:
                if field.key.endswith("_id") and field.key != "order_id":
                    modelx = getattr(models, field.key[:-3].capitalize())
                    models_l.append(modelx)
        queries = self.search(models_l)
        if queries != []:
            query = query.where(queries)
        if user_id and model != models.User:
            query = query.where(models.User.id == user_id)
        if model == models.Product:
            if store_id:
                query = query.where(models.Product.store_id == store_id)
            if category and category != "all":
                query = query.where(models.Product.category == category)
            if min_price:
                query = query.where(models.Product.price >= min_price)
            if max_price:
                query = query.where(models.Product.price <= max_price)

        count, data = await asyncio.gather(
            self.get_count(query), self.get_list(query.group_by(model.id))
        )
        if postprocess:
            data = await postprocess(data)
        return {
            "count": count,
            "next": self.get_next_url(count),
            "previous": self.get_previous_url(),
            "result": data,
        }
