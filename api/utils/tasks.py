import asyncio

from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


def create_task(
    coroutine,
    *,
    loop=None,
):
    if loop is None:  # pragma: no cover
        loop = asyncio.get_running_loop()
    task = loop.create_task(coroutine)
    task.add_done_callback(check_task_errors)
    return task


def check_task_errors(task):
    try:
        task.result()
    except asyncio.CancelledError:
        pass  # Task cancellation should not be logged as an error.
    except Exception as e:
        logger.error(get_exception_message(e))
