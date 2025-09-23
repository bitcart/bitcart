from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, NewType, Protocol

from fastapi import Request
from fastapi.security import SecurityScopes
from taskiq import AsyncTaskiqDecoratedTask, AsyncTaskiqTask
from taskiq.scheduler.created_schedule import CreatedSchedule
from taskiq.scheduler.scheduled_task import CronSpec
from taskiq_redis import RedisStreamBroker

from api.schemas.base import Schema

if TYPE_CHECKING:
    from api import models


type Money = str
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


class TasksBroker(RedisStreamBroker):
    def get_task(self, task_name: str) -> AsyncTaskiqDecoratedTask[Any, Any]:
        task = self.find_task(task_name)
        if task is None:
            raise ValueError(f"Task {task_name} not found")
        return task

    async def publish(
        self,
        task_name: str,
        data: Schema,
    ) -> AsyncTaskiqTask[Any]:
        task = self.get_task(task_name)
        return await task.kiq(data)

    async def schedule_by_time(self, task_name: str, time: datetime, *args: Any, **kwargs: Any) -> CreatedSchedule[Any]:
        from api.tasks import redis_scheduler_source

        task = self.get_task(task_name)
        return await task.schedule_by_time(redis_scheduler_source, time, *args, **kwargs)

    async def schedule_by_cron(self, task_name: str, cron: str | CronSpec, *args: Any, **kwargs: Any) -> CreatedSchedule[Any]:
        from api.tasks import redis_scheduler_source

        task = self.get_task(task_name)
        return await task.schedule_by_cron(redis_scheduler_source, cron, *args, **kwargs)


ClientTasksBroker = NewType("ClientTasksBroker", TasksBroker)


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
