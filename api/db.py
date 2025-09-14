import contextlib
from collections.abc import AsyncIterator
from typing import Literal

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
)

from api.settings import Settings


def create_async_engine_core(
    *,
    dsn: str,
    application_name: str | None = None,
    pool_size: int | None = None,
    pool_recycle: int | None = None,
    debug: bool = False,
) -> AsyncEngine:
    return _create_async_engine(
        dsn,
        echo=debug,
        connect_args={"server_settings": {"application_name": application_name}} if application_name else {},
        pool_size=pool_size,
        pool_recycle=pool_recycle,
    )


type AsyncSessionMaker = async_sessionmaker[AsyncSession]

type ProcessName = Literal["app", "worker", "test", "migrations"]


def create_async_engine(settings: Settings, process_name: ProcessName = "app", dsn: str | None = None) -> AsyncEngine:
    return create_async_engine_core(
        dsn=dsn or str(settings.postgres_dsn),
        application_name=f"{settings.ENV.value}.{process_name}",
        debug=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )


def create_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session(
    sessionmaker: AsyncSessionMaker,
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        exc = yield session
        if exc is not None:
            await session.rollback()
        else:
            with contextlib.suppress(Exception):
                await session.commit()


__all__ = [
    "AsyncSession",
    "AsyncEngine",
    "Engine",
    "AsyncSessionMaker",
    "create_async_engine",
    "create_async_sessionmaker",
]
