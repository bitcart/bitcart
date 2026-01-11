import asyncio
import contextlib
import functools
import platform
import signal
import sys
from datetime import timedelta
from multiprocessing import Process

import sqlalchemy
from alembic import config, script
from alembic.runtime import migration
from dishka import AsyncContainer
from dishka.integrations.taskiq import setup_dishka
from taskiq import TaskiqEvents, TaskiqState
from taskiq.api import run_receiver_task, run_scheduler_task

from api import constants
from api.db import create_async_engine
from api.ioc import build_container
from api.ioc.worker import WorkerProvider
from api.logging import configure as configure_logging
from api.logging import get_logger
from api.sentry import configure_sentry
from api.services.coins import CoinService
from api.services.notification_manager import NotificationManager
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.tasks import broker, scheduler
from api.types import TasksBroker
from api.utils.common import excepthook_handler, handle_event_loop_exception

logger = get_logger("worker")


def check_revision(conn: sqlalchemy.engine.Connection, script_dir: script.ScriptDirectory) -> bool:
    context = migration.MigrationContext.configure(conn)
    return context.get_current_revision() == script_dir.get_current_head()


async def check_db() -> bool:
    try:
        settings = Settings(IS_WORKER=True)
        if settings.is_testing():
            return True
        engine = create_async_engine(settings, "migrations")
        alembic_cfg = config.Config("alembic.ini")
        script_dir = script.ScriptDirectory.from_config(alembic_cfg)
        async with engine.begin() as conn:
            return await conn.run_sync(functools.partial(check_revision, script_dir=script_dir))
        await engine.dispose()
        return True
    except Exception:
        return False


async def lifespan_start(container: AsyncContainer, process: Process, state: TaskiqState) -> None:
    state.process = process
    sys.excepthook = excepthook_handler(logger, sys.excepthook)
    asyncio.get_running_loop().set_exception_handler(
        lambda *args, **kwargs: handle_event_loop_exception(logger, *args, **kwargs)
    )
    plugin_registry = await container.get(PluginRegistry)
    await plugin_registry.startup()
    await plugin_registry.worker_setup()
    for service in WorkerProvider.TO_PRELOAD:
        await container.get(service)
    settings = await container.get(Settings)
    coin_service = await container.get(CoinService)
    notification_manager = await container.get(NotificationManager)
    logger.info(f"Bitcart version: {constants.VERSION} - {constants.WEBSITE} - {constants.GIT_REPO_URL}")
    logger.info(f"Python version: {sys.version}. On platform: {platform.platform()}")
    logger.info(
        f"BITCART_CRYPTOS={','.join(list(settings.ENABLED_CRYPTOS))}; IN_DOCKER={settings.DOCKER_ENV}; "
        f"LOG_FILE={settings.LOG_FILE_NAME}"
    )
    logger.info(f"Successfully loaded {len(coin_service.cryptos)} cryptos")
    logger.info(f"{len(notification_manager.notifiers)} notification providers available")
    state.scheduler_task = asyncio.create_task(run_scheduler_task(scheduler, interval=timedelta(seconds=1)))


async def lifespan_stop(container: AsyncContainer, state: TaskiqState) -> None:
    state.scheduler_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await state.scheduler_task
    plugin_registry = await container.get(PluginRegistry)
    await plugin_registry.shutdown()
    await container.close()
    state.process.terminate()


def get_app(process: Process) -> TasksBroker:
    settings = Settings(IS_WORKER=True)
    configure_sentry(settings)
    configure_logging(settings=settings)
    container = build_container(settings, extra_providers=(WorkerProvider(),))
    broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, functools.partial(lifespan_start, container, process))
    broker.add_event_handler(TaskiqEvents.WORKER_SHUTDOWN, functools.partial(lifespan_stop, container))
    setup_dishka(container, broker)
    return broker


async def _run_broker_core(broker: TasksBroker, stop_event: asyncio.Event | None) -> None:
    broker.is_worker_process = True
    await broker.startup()
    receiver_task = asyncio.create_task(run_receiver_task(broker))
    try:
        if stop_event is None:
            with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
                await receiver_task
        else:
            stopper_task = asyncio.create_task(stop_event.wait())
            await asyncio.wait({receiver_task, stopper_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        receiver_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await receiver_task
        await broker.shutdown()


async def start_broker_basic(broker: TasksBroker) -> None:
    await _run_broker_core(broker, stop_event=None)


async def start_broker(broker: TasksBroker) -> None:
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop_event.set())
    await _run_broker_core(broker, stop_event=stop_event)


async def wait_loop() -> None:
    while True:
        if await check_db():
            break
        print("Database not available/not migrated, waiting...")  # noqa: T201
        await asyncio.sleep(1)
