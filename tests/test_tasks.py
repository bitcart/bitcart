import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

import pytest
from redis.asyncio import Redis

from api.schemas.tasks import AgentCallMessage, PluginTaskMessage
from api.services.host_agent import CALL_TIMEOUT
from api.settings import Settings
from api.types import BaseTasksBroker, ClientTasksBroker, TasksBroker
from api.worker import start_broker_basic

pytestmark = pytest.mark.anyio


@pytest.fixture
async def stream_broker(settings: Settings) -> AsyncIterator[TasksBroker]:
    broker = TasksBroker(url=settings.redis_url, queue_name=f"test_tasks_{uuid.uuid4().hex}", xread_block=100)
    yield broker
    async with Redis(connection_pool=broker.connection_pool) as redis:
        await redis.delete(broker.queue_name)
    await broker.connection_pool.disconnect()


@contextlib.asynccontextmanager
async def running(broker: BaseTasksBroker) -> AsyncGenerator[None]:
    task = asyncio.create_task(start_broker_basic(broker))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def wait_until(condition: Callable[[], Awaitable[bool]]) -> None:
    async with asyncio.timeout(5):
        while not await condition():
            await asyncio.sleep(0.01)


async def wait_drained(broker: TasksBroker) -> None:
    async def drained() -> bool:
        async with Redis(connection_pool=broker.connection_pool) as redis:
            groups = await redis.xinfo_groups(broker.queue_name)
            stream = await redis.xinfo_stream(broker.queue_name)
        return bool(groups) and groups[0]["pending"] == 0 and groups[0]["last-delivered-id"] == stream["last-generated-id"]

    await wait_until(drained)


async def test_task_queued_while_worker_is_down_runs_on_start(stream_broker: TasksBroker) -> None:
    calls: list[str] = []

    @stream_broker.task("sync_wallet")
    async def sync_wallet(wallet_id: str) -> None:
        calls.append(wallet_id)

    await sync_wallet.kiq("wallet")
    async with running(stream_broker):
        await wait_drained(stream_broker)
    assert calls == ["wallet"]


async def test_expired_agent_call_is_dropped(stream_broker: TasksBroker) -> None:
    commands: list[str] = []

    @stream_broker.task("agent_call")
    async def agent_call(params: AgentCallMessage) -> None:
        commands.append(params.command)

    await stream_broker.publish("agent_call", AgentCallMessage(command="expired"), expires_in=0.1)
    await stream_broker.publish("agent_call", AgentCallMessage(command="fresh"), expires_in=CALL_TIMEOUT)
    await asyncio.sleep(0.2)
    async with running(stream_broker):
        await wait_drained(stream_broker)
    assert commands == ["fresh"]


async def test_worker_recovers_when_redis_loses_the_stream(stream_broker: TasksBroker) -> None:
    calls: list[str] = []

    @stream_broker.task("sync_wallet")
    async def sync_wallet(wallet_id: str) -> None:
        calls.append(wallet_id)

    async with running(stream_broker):
        await sync_wallet.kiq("before")
        await wait_drained(stream_broker)
        async with Redis(connection_pool=stream_broker.connection_pool) as redis:
            await redis.delete(stream_broker.queue_name)
        await sync_wallet.kiq("after")
        await wait_drained(stream_broker)
    assert calls == ["before", "after"]


@pytest.mark.parametrize(("completed", "expected_calls"), [(True, 0), (False, 1)])
async def test_redelivery_after_crash(stream_broker: TasksBroker, completed: bool, expected_calls: int) -> None:
    calls: list[str] = []

    @stream_broker.task("send_notification")
    async def send_notification(text: str) -> None:
        calls.append(text)

    task = await send_notification.kiq("hello")
    await stream_broker.startup()
    # a worker receives the task and dies without acking it, either after it finished or in the middle of it
    async with Redis(connection_pool=stream_broker.connection_pool) as redis:
        await redis.xreadgroup(stream_broker.consumer_group_name, "dead-worker", {stream_broker.queue_name: ">"})
    if completed:
        await stream_broker.mark_done(task.task_id)
    stream_broker.idle_timeout = 0
    async with running(stream_broker):
        # taskiq-redis only reclaims pending tasks after a read that returned new ones
        await send_notification.kiq("next")
        await wait_drained(stream_broker)
    assert calls.count("hello") == expected_calls


async def test_client_tasks_reach_every_api_process(settings: Settings) -> None:
    queue_name = f"test_client_tasks_{uuid.uuid4().hex}"
    brokers = [ClientTasksBroker(url=settings.redis_url, queue_name=queue_name) for _ in range(2)]
    received: list[int] = []

    def register(broker: ClientTasksBroker, process: int) -> None:
        @broker.task("plugin_task_client")
        async def plugin_task_client(params: PluginTaskMessage) -> None:
            received.append(process)

    for process, broker in enumerate(brokers):
        register(broker, process)
    async with running(brokers[0]), running(brokers[1]), Redis.from_url(settings.redis_url) as redis:

        async def subscribed() -> bool:
            return (await redis.pubsub_numsub(queue_name))[0][1] == len(brokers)

        await wait_until(subscribed)
        await brokers[0].publish("plugin_task_client", PluginTaskMessage(event="event", data={}))

        async def received_by_all() -> bool:
            return len(received) == len(brokers)

        await wait_until(received_by_all)
    assert sorted(received) == [0, 1]
