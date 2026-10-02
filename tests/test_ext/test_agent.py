from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from api.ext.agent import AgentClient, AgentError, encode_request
from tests.fixtures.pytest.agent import FakeAgent

pytestmark = pytest.mark.anyio


@pytest.fixture
async def agent() -> AsyncIterator[FakeAgent]:
    agent = FakeAgent()
    yield agent
    await agent.stop()


def test_encode_request() -> None:
    assert encode_request("ping", {}) == b"ping\0\0"
    assert encode_request("backup", {"BACKUP_PROVIDER": "s3", "S3_KEY": "a=b c"}) == (
        b"backup\0BACKUP_PROVIDER=s3\0S3_KEY=a=b c\0\0"
    )
    for value in ("a\0restore", "a\nb", "\x7f"):
        with pytest.raises(AgentError) as exc_info:
            encode_request("backup", {"BACKUP_NAME": value})
        assert exc_info.value.code == "invalid_argument"
        assert exc_info.value.field == "BACKUP_NAME"
    for key in ("", "BACKUP_PROVIDER=scp"):
        with pytest.raises(AgentError) as exc_info:
            encode_request("backup", {key: "x"})
        assert exc_info.value.message == "invalid argument name"


async def test_unix_transport(agent: FakeAgent) -> None:
    client = AgentClient(await agent.start_unix())
    response = await client.call("capabilities")
    assert response.data["protocol"] == 1
    assert response.log == b""
    job_id = (await client.call("update", {"channel": "staging"})).data["job_id"]
    assert agent.requests[-1] == ("update", {"channel": "staging"})
    with pytest.raises(AgentError) as exc_info:
        await client.call("restart")
    assert exc_info.value.code == "busy"
    assert exc_info.value.job_id == job_id
    log = b"line 1\n\xff\xfe invalid utf-8\nlast line\n"
    agent.finish(job_id, log=log, result={"filename": "a.tar.zst"})
    response = await client.call("job_status", {"id": job_id, "log_lines": "all"})
    assert response.data["state"] == "done"
    assert response.data["result"] == {"filename": "a.tar.zst"}
    assert response.log == log


async def test_tcp_transport(agent: FakeAgent) -> None:
    agent.token = "secret"
    url = await agent.start_tcp()
    assert (await AgentClient(url, token="secret").call("ping")).data == {}
    assert agent.requests[-1] == ("ping", {"auth": "secret"})
    with pytest.raises(AgentError) as exc_info:
        await AgentClient(url, token="wrong").call("ping")
    assert exc_info.value.code == "unauthorized"


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (b"", "connection closed"),
        (b"x" * 70000 + b"\n", "response too long"),
        (b"not json\n", "not JSON"),
        (b"[]\n", "unexpected format"),
        (b'{"v":2,"ok":true,"data":{}}\n', "Unsupported host agent protocol version: 2"),
        (b'{"v":1,"ok":false}\n', "unexpected format"),
        (b'{"v":1,"ok":true,"data":[]}\n', "unexpected format"),
        (b'{"v":1,"ok":true,"data":{"state":"done","log_bytes":10}}\nshort', "truncated log"),
        (b'{"v":1,"ok":true,"data":{"state":"done"}}\n', "missing log size"),
    ],
)
async def test_invalid_responses(agent: FakeAgent, reply: bytes, message: str) -> None:
    agent.raw_reply = reply
    with pytest.raises(AgentError) as exc_info:
        await AgentClient(await agent.start_unix()).call("job_status", {"id": "20260101T000000Z-000000"})
    assert exc_info.value.code == "unavailable"
    assert message in exc_info.value.message


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://localhost", "Unsupported host agent URL scheme: http"),
        ("unix:///nonexistent/agent.sock", "Could not reach the host agent: "),
    ],
)
async def test_invalid_settings(url: str, message: str) -> None:
    with pytest.raises(AgentError) as exc_info:
        await AgentClient(url).call("ping")
    assert exc_info.value.code == "unavailable"
    assert exc_info.value.message.startswith(message)


async def test_timeout(agent: FakeAgent, monkeypatch: pytest.MonkeyPatch) -> None:
    async def hang(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(agent, "handle", hang)
    with pytest.raises(AgentError) as exc_info:
        await AgentClient(await agent.start_unix(), timeout=0.2).call("ping")
    assert exc_info.value.message == "The host agent did not respond in time"
