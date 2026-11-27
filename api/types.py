import time
from collections.abc import AsyncGenerator, Iterator
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Literal, Protocol, cast

from fastapi import Request
from fastapi.security import SecurityScopes
from pydantic import Field
from redis.asyncio import Redis, ResponseError
from taskiq import (
    AckableMessage,
    AsyncBroker,
    AsyncTaskiqDecoratedTask,
    AsyncTaskiqTask,
    TaskiqMessage,
    TaskiqMiddleware,
    TaskiqResult,
)
from taskiq.scheduler.created_schedule import CreatedSchedule
from taskiq.scheduler.scheduled_task import CronSpec
from taskiq.utils import maybe_awaitable
from taskiq_redis import PubSubBroker, RedisStreamBroker

from api.logging import get_logger
from api.schemas.base import Schema

if TYPE_CHECKING:
    from api import models

logger = get_logger(__name__)


type Money = Annotated[
    str,
    Field(
        description="Amount in a currency: a decimal string already rounded and padded to the currency's decimal places."
        " Display it without rounding it again.",
        examples=["25.00", "0.00150000"],
    ),
]
type Quotes = dict[str, Decimal]
type PayoutAmount = Decimal | Literal["!"]


class StrEnumMeta(type):
    __enum_fields__: list[str]

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> type:
        new_class = type.__new__(cls, name, bases, attrs)
        new_class.__enum_fields__ = [
            x.lower() for x in [getattr(new_class, attr) for attr in dir(new_class) if attr.upper() == attr]
        ]
        return new_class

    def __contains__(cls, v: str) -> bool:
        return v in cls.__enum_fields__

    def __iter__(cls) -> Iterator[str]:
        return iter(cls.__enum_fields__)


class StrEnum(metaclass=StrEnumMeta):
    pass


class BaseTasksBroker(AsyncBroker):
    def get_task(self, task_name: str) -> AsyncTaskiqDecoratedTask[Any, Any]:
        task = self.find_task(task_name)
        if task is None:
            raise ValueError(f"Task {task_name} not found")
        return task

    async def publish(self, task_name: str, data: Schema, *, expires_in: float | None = None) -> AsyncTaskiqTask[Any]:
        kicker = self.get_task(task_name).kicker()
        if expires_in is not None:
            kicker = kicker.with_labels(deadline=time.time() + expires_in)
        return await kicker.kiq(data)

    async def schedule_by_time(self, task_name: str, time: datetime, *args: Any, **kwargs: Any) -> CreatedSchedule[Any]:
        from api.tasks import redis_scheduler_source

        task = self.get_task(task_name)
        return await task.schedule_by_time(redis_scheduler_source, time, *args, **kwargs)

    async def schedule_by_cron(self, task_name: str, cron: str | CronSpec, *args: Any, **kwargs: Any) -> CreatedSchedule[Any]:
        from api.tasks import redis_scheduler_source

        task = self.get_task(task_name)
        return await task.schedule_by_cron(redis_scheduler_source, cron, *args, **kwargs)


TASK_DONE_KEY = "tasks:done:{}"
TASK_DONE_TTL = 24 * 60 * 60


class TaskDoneMiddleware(TaskiqMiddleware):
    # runs before the result is saved and the message is acked, so a task finished right before a crash isn't rerun
    async def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        if not result.is_err:
            await cast(TasksBroker, self.broker).mark_done(message.task_id)


# Tasks wait in a redis stream and the worker acks each one after it finishes,
# so a task left unacked by a dead worker is redelivered after idle_timeout
class TasksBroker(BaseTasksBroker, RedisStreamBroker):
    def __init__(self, url: str, **kwargs: Any) -> None:
        # acked entries stay in the stream, so it is capped. A group created after tasks were queued
        # (e.g. redis was restarted) reads them from the start instead of skipping them
        super().__init__(url, maxlen=10_000, consumer_id="0", **kwargs)
        self.add_middlewares(TaskDoneMiddleware())

    async def listen(self) -> AsyncGenerator[AckableMessage]:
        while True:
            try:
                async for message in super().listen():
                    if await self.should_skip(message.data):
                        await maybe_awaitable(message.ack())
                        continue
                    yield message
            except ResponseError as e:
                # redis lost the stream along with the group, e.g. it was restarted without persistence
                if not str(e).startswith("NOGROUP"):
                    raise
                await self._declare_consumer_group()

    async def should_skip(self, data: bytes) -> bool:
        try:
            message = self.formatter.loads(data)
            message.parse_labels()
        except Exception:
            return False  # the receiver reports it
        deadline = message.labels.get("deadline")
        if deadline is not None and time.time() > deadline:
            logger.info(f"Dropping task {message.task_name} {message.task_id}: its caller has stopped waiting")
            return True
        async with Redis(connection_pool=self.connection_pool) as redis:
            if await redis.exists(TASK_DONE_KEY.format(message.task_id)):
                logger.info(f"Skipping task {message.task_name} {message.task_id}: it has already completed")
                return True
        return False

    async def mark_done(self, task_id: str) -> None:
        async with Redis(connection_pool=self.connection_pool) as redis:
            await redis.set(TASK_DONE_KEY.format(task_id), 1, ex=TASK_DONE_TTL)


# pubsub, so that every API process gets each task
class ClientTasksBroker(BaseTasksBroker, PubSubBroker):
    pass


class AuthServiceProtocol(Protocol):
    async def find_user_and_check_permissions(
        self,
        header_token: str | None,
        security_scopes: SecurityScopes,
        request: Request | None = None,
    ) -> tuple["models.User", "models.Token"]: ...


class PasswordHasherProtocol(Protocol):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool: ...
    def get_password_hash(self, password: str) -> str: ...
