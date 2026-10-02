from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import tempfile
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_mock
from fastapi import FastAPI
from filelock import FileLock

from api import utils
from api.ext.agent import AgentClient
from api.services.backup_manager import BackupManager
from api.services.ext.configurator import ConfiguratorService
from api.services.host_agent import LAST_JOBS_KEY, STATE_KEY, HostAgentService

COMMANDS = [
    "capabilities",
    "ping",
    "get_config",
    "job_status",
    "restart",
    "reload",
    "cleanup",
    "update",
    "backup",
    "restore",
    "reconfigure",
]
JOB_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{6}")
BACKUP_KEY = re.compile(r"(BACKUP|S3|SCP)_[A-Z0-9_]+")
AGENT_LOCK = os.path.join(tempfile.gettempdir(), "bitcart-tests-host-agent.lock")


class FakeAgent:
    def __init__(self, token: str = "") -> None:
        self.token = token
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.jobs: dict[str, dict[str, Any]] = {}
        self.running: str | None = None
        self.settings = {
            "BITCART_HOST": "shop.example.com",
            "BITCART_CRYPTOS": "btc,ltc",
            "LTC_NETWORK": "testnet",
            "BITCART_INSTALL": "",
        }
        self.raw_reply: bytes | None = None
        self.commands = COMMANDS
        self.directory = tempfile.mkdtemp(prefix="agent")
        self.path = os.path.join(self.directory, "agent.sock")
        self.server: asyncio.Server | None = None

    async def start_unix(self) -> str:
        self.server = await asyncio.start_unix_server(self.handle, self.path)
        return f"unix://{self.path}"

    async def start_tcp(self) -> str:
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        return f"tcp://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        shutil.rmtree(self.directory, ignore_errors=True)

    def start_job(self, command: str, args: dict[str, str]) -> str:
        job_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
        self.jobs[job_id] = {"command": command, "state": "running", "args": args, "log": b"", "result": None}
        self.running = job_id
        return job_id

    def finish(self, job_id: str, state: str = "done", log: bytes = b"", result: dict[str, Any] | None = None) -> None:
        self.jobs[job_id].update(state=state, log=log, result=result)
        if state == "failed":
            self.jobs[job_id]["reason"] = "exit"
        self.running = None

    def respond(self, command: str, args: dict[str, str]) -> tuple[dict[str, Any], bytes]:
        if self.token and args.pop("auth", None) != self.token:
            return {"ok": False, "error": {"code": "unauthorized", "message": "authentication failed"}}, b""
        if command not in self.commands:
            return {"ok": False, "error": {"code": "unknown_command", "message": "unknown command"}}, b""
        if command == "capabilities":
            return {"ok": True, "data": {"protocol": 1, "commands": self.commands, "running_job": self.running}}, b""
        if command == "ping":
            return {"ok": True, "data": {}}, b""
        if command == "get_config":
            return {"ok": True, "data": {"settings": self.settings}}, b""
        if command == "job_status":
            return self.job_status(args)
        if command == "backup" and (invalid := next((k for k in args if not BACKUP_KEY.fullmatch(k)), None)):
            return {"ok": False, "error": {"code": "invalid_argument", "message": "unknown argument", "field": invalid}}, b""
        if self.running:
            error = {"code": "busy", "message": "another job is running", "job_id": self.running}
            return {"ok": False, "error": error}, b""
        return {"ok": True, "data": {"job_id": self.start_job(command, args)}}, b""

    def job_status(self, args: dict[str, str]) -> tuple[dict[str, Any], bytes]:
        job_id = args.get("id", "")
        if not JOB_ID.fullmatch(job_id):
            return {"ok": False, "error": {"code": "invalid_argument", "message": "id is not a job id", "field": "id"}}, b""
        if job_id not in self.jobs:
            return {"ok": False, "error": {"code": "not_found", "message": "no such job"}}, b""
        job = self.jobs[job_id]
        log = job["log"]
        if (lines := args.get("log_lines", "50")) != "all":
            tail = log.splitlines(keepends=True)
            log = b"".join(tail[max(len(tail) - int(lines), 0) :])
        data = {
            "id": job_id,
            "command": job["command"],
            "state": job["state"],
            "created": 1790172411,
            "result": job["result"],
            "log_bytes": len(log),
            "log_complete": len(log) == len(job["log"]),
        }
        if "reason" in job:
            data["reason"] = job["reason"]
        return {"ok": True, "data": data}, log

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        fields = []
        while (field := await reader.readuntil(b"\0")) != b"\0":
            fields.append(field[:-1].decode())
        command, args = fields[0], dict(field.split("=", 1) for field in fields[1:])
        self.requests.append((command, dict(args)))
        if self.raw_reply is not None:
            writer.write(self.raw_reply)
        else:
            reply, tail = self.respond(command, args)
            writer.write(json.dumps({"v": 1, **reply}).encode() + b"\n" + tail)
        await writer.drain()
        writer.close()


@pytest.fixture
def agent_lock() -> Iterator[None]:
    with FileLock(AGENT_LOCK):
        yield


@pytest.fixture
def background_tasks(mocker: pytest_mock.MockerFixture) -> MagicMock:
    return mocker.spy(utils.tasks, "create_task")


@pytest.fixture
async def host_agent(app: FastAPI, agent_lock: None, background_tasks: MagicMock) -> AsyncIterator[HostAgentService]:
    service = await app.state.dishka_container.get(HostAgentService)
    await app.state.dishka_container.get(BackupManager)
    await app.state.dishka_container.get(ConfiguratorService)
    await service.redis_pool.delete(STATE_KEY, LAST_JOBS_KEY)
    yield service
    await asyncio.gather(*background_tasks.spy_return_list)
    await service.redis_pool.delete(STATE_KEY, LAST_JOBS_KEY)


@pytest.fixture
async def fake_agent(host_agent: HostAgentService) -> AsyncIterator[FakeAgent]:
    agent = FakeAgent()
    host_agent.client = AgentClient(await agent.start_unix())
    await host_agent.refresh_state()
    yield agent
    await agent.stop()
