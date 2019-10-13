# pylint: disable=no-member
import asyncio
from typing import Callable, Optional, Union

from fastapi import Query
from starlette.requests import Request

from .db import db


class PaginationMeta(type):
    def __new__(mcs, name, bases, namespace, *args, **kwargs):
        cls = super(PaginationMeta, mcs).__new__(mcs, name, bases, namespace)
        _cls__init__ = cls.__init__

        def __init__(
            self,
            request: Request,
            offset: int = Query(default=cls.default_offset, ge=0, le=cls.max_offset),
            limit: int = Query(default=cls.default_limit, ge=1, le=cls.max_limit),
        ):
            _cls__init__(self, request, offset, limit)

        setattr(cls, "__init__", __init__)
        return cls


class Pagination(metaclass=PaginationMeta):
    default_offset = 0
    default_limit = 5
    max_offset = None
    max_limit = 1000

    def __init__(
        self,
        request: Request,
        offset: int = Query(default=default_offset, ge=0, le=max_offset),
        limit: int = Query(default=default_limit, ge=1, le=max_limit),
    ):
        self.request = request
        self.offset = offset
        self.limit = limit
        self.model = None

    async def get_count(self) -> int:
        return await db.func.count(self.model.id).gino.scalar()  # type: ignore

    def get_next_url(self, count) -> Union[None, str]:
        if self.offset + self.limit >= count:
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

    async def get_list(self) -> list:
        return (
            await self.model.query.limit(self.limit)  # type: ignore
            .offset(self.offset)
            .gino.all()
        )

    async def paginate(self, model, postprocess: Optional[Callable] = None) -> dict:
        self.model = model
        count, data = await asyncio.gather(self.get_count(), self.get_list())
        if postprocess:
            data = await postprocess(data)
        return {
            "count": count,
            "next": self.get_next_url(count),
            "previous": self.get_previous_url(),
            "result": data,
        }
