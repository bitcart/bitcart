import asyncio
from collections.abc import Coroutine
from typing import Any

from api.logging import get_exception_message, get_logger

logger = get_logger(__name__)


def create_task(
    coroutine: Coroutine[Any, Any, Any],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
) -> asyncio.Task[Any]:
    if loop is None:  # pragma: no cover
        loop = asyncio.get_running_loop()
    task = loop.create_task(coroutine)
    task.add_done_callback(check_task_errors)
    return task


def check_task_errors(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass  # Task cancellation should not be logged as an error.
    except Exception as e:
        logger.error(get_exception_message(e))
