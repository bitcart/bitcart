import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from taskiq.exceptions import TaskiqResultTimeoutError

from api import utils
from api.constants import DOCKER_REPO_URL
from api.ext.agent import AgentClient, AgentError, AgentErrorCode
from api.logging import get_logger, log_errors
from api.redis import Redis
from api.schemas.misc import HostAgentJob, HostAgentOverview, HostAgentState
from api.schemas.tasks import AgentCallMessage
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)

STATE_KEY = "agent:capabilities"
LAST_JOBS_KEY = "agent:last_job"
CALL_TIMEOUT = 45
REFRESH_INTERVAL = 5 * 60
STALE_STATE_SECONDS = 2 * REFRESH_INTERVAL
JOB_POLL_INTERVAL = 5
AGENT_JOB_SECONDS = 2 * 60 * 60
JOB_WATCH_SECONDS = AGENT_JOB_SECONDS + 10 * 60
AGENT_DOCS_URL = f"{DOCKER_REPO_URL}#host-agent"


def error_response(error: AgentError) -> dict[str, Any]:
    if error.code == AgentErrorCode.BUSY:
        return {"status": "error", "message": "Another server operation is running", "job_id": error.job_id}
    if error.code == AgentErrorCode.INVALID_ARGUMENT:
        return {"status": "error", "message": f"Invalid {error.field}: {error.message}"}
    return {"status": "error", "message": error.message}


def unavailable_reason(state: HostAgentState) -> str | None:
    if state.checked_at is None:
        return "the worker has not checked it yet"
    if time.time() - state.checked_at > STALE_STATE_SECONDS:
        return "the worker has not checked it recently"
    if not state.available or state.capabilities is None:
        return state.error or "not configured"
    return None


def job_deadline(job_id: str) -> float:
    created = datetime.strptime(job_id[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    return created.timestamp() + JOB_WATCH_SECONDS


class HostAgentService:
    def __init__(
        self,
        settings: Settings,
        client: AgentClient,
        redis_pool: Redis,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
    ) -> None:
        self.settings = settings
        self.client = client
        self.redis_pool = redis_pool
        self.broker = broker
        self.plugin_registry = plugin_registry
        self.job_lock = asyncio.Lock()

    async def start(self) -> None:
        asyncio.create_task(utils.common.run_repeated(self.refresh, REFRESH_INTERVAL, initial_delay=0))
        asyncio.create_task(utils.common.run_repeated(self.check_jobs, JOB_POLL_INTERVAL))

    async def call(self, command: str, args: dict[str, str] | None = None) -> dict[str, Any]:
        if self.settings.IS_WORKER or self.settings.is_testing():
            reply = await self.handle_call(command, args or {})
        else:
            reply = await self._call_worker(command, args or {})
        if not reply["ok"]:
            raise AgentError(**reply["error"])
        return reply["data"]

    async def _call_worker(self, command: str, args: dict[str, str]) -> dict[str, Any]:
        task = await self.broker.publish("agent_call", AgentCallMessage(command=command, args=args))
        try:
            result = await task.wait_result(check_interval=0.01, timeout=CALL_TIMEOUT)
        except TaskiqResultTimeoutError:
            return {"ok": False, "error": AgentError(AgentErrorCode.UNAVAILABLE, "The worker did not respond").to_dict()}
        if result.is_err:
            return {
                "ok": False,
                "error": AgentError(AgentErrorCode.UNAVAILABLE, "The worker could not call the host agent").to_dict(),
            }
        return result.return_value

    async def handle_call(self, command: str, args: dict[str, str]) -> dict[str, Any]:
        try:
            data = await self.call_agent(command, args)
        except AgentError as e:
            return {"ok": False, "error": e.to_dict()}
        if "job_id" in data:
            async with self.job_lock:
                previous = await self.get_job(command)
                await self.set_job(HostAgentJob(job_id=data["job_id"], command=command))
            if previous is not None and previous.state == "running":
                utils.tasks.create_task(self.complete_replaced_job(previous))
        return {"ok": True, "data": data}

    async def call_agent(self, command: str, args: dict[str, str] | None = None) -> dict[str, Any]:
        response = await self.client.call(command, args)
        if command == "job_status":
            response.data["log"] = response.log.decode(errors="replace")
        return response.data

    async def get_state(self) -> HostAgentState:
        data = await self.redis_pool.get(STATE_KEY)
        return HostAgentState.model_validate_json(data) if data else HostAgentState()

    async def require(self, command: str) -> None:
        state = await self.get_state()
        if (reason := unavailable_reason(state)) is not None:
            raise AgentError(AgentErrorCode.UNAVAILABLE, f"The host agent is unavailable: {reason}. See {AGENT_DOCS_URL}")
        if command not in (state.capabilities or {}).get("commands", []):
            raise AgentError(
                AgentErrorCode.UNKNOWN_COMMAND, f"The host agent does not support {command}. Update the server to use it"
            )

    async def running_job(self) -> str | None:
        return ((await self.get_state()).capabilities or {}).get("running_job")

    async def job_status(self, job_id: str, log_lines: str = "50") -> dict[str, Any]:
        await self.require("job_status")
        return await self.call("job_status", {"id": job_id, "log_lines": log_lines})

    async def overview(self) -> HostAgentOverview:
        return HostAgentOverview(state=await self.get_state(), jobs=await self.get_jobs())

    async def get_job(self, command: str) -> HostAgentJob | None:
        data = await self.redis_pool.hget(LAST_JOBS_KEY, command)
        return HostAgentJob.model_validate_json(data) if data else None

    async def get_jobs(self) -> dict[str, HostAgentJob]:
        records = await self.redis_pool.hgetall(LAST_JOBS_KEY)
        jobs = (HostAgentJob.model_validate_json(data) for data in records.values())
        return {job.command: job for job in jobs}

    async def refresh_state(self) -> HostAgentState:
        previous = await self.get_state()
        state = HostAgentState(configured=self.client.configured, checked_at=int(time.time()))
        try:
            state.capabilities = await self.call_agent("capabilities")
            state.available = True
            if previous.unreachable_since is not None:
                logger.info("Host agent is reachable again")
        except AgentError as e:
            if state.configured:
                state.error = e.message
                state.capabilities = previous.capabilities
                state.unreachable_since = previous.unreachable_since or state.checked_at
                if previous.unreachable_since is None:
                    logger.warning(f"Host agent is unreachable: {e.message}")
        await self.redis_pool.set(STATE_KEY, state.model_dump_json())
        return state

    async def refresh(self) -> None:
        with log_errors(logger):
            await self.refresh_state()

    async def set_job(self, job: HostAgentJob) -> None:
        await self.redis_pool.hset(LAST_JOBS_KEY, job.command, job.model_dump_json())

    async def check_jobs(self) -> None:
        with log_errors(logger):
            for job in (await self.get_jobs()).values():
                if job.state != "running":
                    continue
                try:
                    status = await self.job_status(job.job_id, "0")
                except AgentError as e:
                    if e.code == AgentErrorCode.NOT_FOUND or time.time() > job_deadline(job.job_id):
                        await self.finish_job(job, None)
                    continue
                if status["state"] != "running":
                    await self.finish_job(job, status)

    async def finish_job(self, job: HostAgentJob, status: dict[str, Any] | None) -> None:
        async with self.job_lock:
            current = await self.get_job(job.command)
            if current is None or current.job_id != job.job_id or current.state != "running":
                return
            job = current.model_copy(update={"state": status["state"] if status else "unknown"})
            await self.set_job(job)
        logger.info(f"Host agent job {job.job_id} ({job.command}) finished: {job.state}")
        await self.complete_job(job)

    async def complete_job(self, job: HostAgentJob) -> None:
        await self.plugin_registry.run_hook("host_agent_job_finished", job)
        await self.refresh()

    async def complete_replaced_job(self, job: HostAgentJob) -> None:
        try:
            state = (await self.job_status(job.job_id, "0"))["state"]
        except AgentError:
            state = "unknown"
        await self.complete_job(job.model_copy(update={"state": state}))
