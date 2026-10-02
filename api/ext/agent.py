import asyncio
import contextlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import SplitResult, urlsplit

import paramiko

from api import exceptions

PROTOCOL = 1
TIMEOUT = 30
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class AgentErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN_COMMAND = "unknown_command"
    INVALID_ARGUMENT = "invalid_argument"
    BUSY = "busy"
    NOT_FOUND = "not_found"
    INTERNAL = "internal"
    UNAVAILABLE = "unavailable"  # set by the client: the agent could not be reached


class AgentError(exceptions.BitcartError):
    """Host agent request failed: the agent's error reply, or a client-side failure to reach it"""

    def __init__(self, code: str, message: str, field: str | None = None, job_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.job_id = job_id

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field, "job_id": self.job_id}


@dataclass
class AgentResponse:
    data: dict[str, Any]
    log: bytes = b""


def encode_request(command: str, args: dict[str, str]) -> bytes:
    fields = [command]
    for key, value in args.items():
        if not key or "=" in key:
            raise AgentError(AgentErrorCode.INVALID_ARGUMENT, "invalid argument name", field=key)
        if CONTROL_CHARACTERS.search(key) or CONTROL_CHARACTERS.search(value):
            raise AgentError(AgentErrorCode.INVALID_ARGUMENT, "control characters are not allowed", field=key)
        fields.append(f"{key}={value}")
    return b"".join(field.encode() + b"\0" for field in fields) + b"\0"


def invalid_response(reason: str) -> AgentError:
    return AgentError(AgentErrorCode.UNAVAILABLE, f"Invalid response from the host agent: {reason}")


async def read_response(reader: asyncio.StreamReader, command: str) -> AgentResponse:
    try:
        line = await reader.readuntil(b"\n")
    except asyncio.IncompleteReadError:
        raise invalid_response("connection closed") from None
    except asyncio.LimitOverrunError:
        raise invalid_response("response too long") from None
    try:
        reply = json.loads(line)
    except ValueError:
        raise invalid_response("not JSON") from None
    if not isinstance(reply, dict) or not isinstance(reply.get("ok"), bool):
        raise invalid_response("unexpected format")
    if reply.get("v") != PROTOCOL:
        raise AgentError(AgentErrorCode.UNAVAILABLE, f"Unsupported host agent protocol version: {reply.get('v')}")
    if not reply["ok"]:
        error = reply.get("error")
        if not isinstance(error, dict):
            raise invalid_response("unexpected format")
        raise AgentError(
            str(error.get("code", AgentErrorCode.INTERNAL)),
            str(error.get("message", "")),
            error.get("field"),
            error.get("job_id"),
        )
    data = reply.get("data")
    if not isinstance(data, dict):
        raise invalid_response("unexpected format")
    log = b""
    if command == "job_status":
        try:
            log = await reader.readexactly(int(data["log_bytes"]))
        except (KeyError, TypeError, ValueError):
            raise invalid_response("missing log size") from None
        except asyncio.IncompleteReadError:
            raise invalid_response("truncated log") from None
    return AgentResponse(data, log)


class AgentClient:
    def __init__(self, url: str, token: str = "", ssh_key_file: str = "", timeout: float = TIMEOUT) -> None:
        self.url = url
        self.token = token
        self.ssh_key_file = ssh_key_file
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.url)

    async def call(self, command: str, args: dict[str, str] | None = None) -> AgentResponse:
        if not self.configured:
            raise AgentError(AgentErrorCode.UNAVAILABLE, "The host agent is not configured")
        try:
            async with asyncio.timeout(self.timeout):
                url = urlsplit(self.url)
                args = dict(args or {})
                if url.scheme == "tcp":
                    args["auth"] = self.token
                request = encode_request(command, args)
                if url.scheme == "ssh":  # pragma: no cover
                    return await self._call_ssh(url, command, request)
                return await self._call_socket(url, command, request)
        except AgentError:
            raise
        except TimeoutError:
            raise AgentError(AgentErrorCode.UNAVAILABLE, "The host agent did not respond in time") from None
        except Exception as e:
            raise AgentError(AgentErrorCode.UNAVAILABLE, f"Could not reach the host agent: {e}") from None

    async def _call_socket(self, url: SplitResult, command: str, request: bytes) -> AgentResponse:
        if url.scheme == "unix":
            reader, writer = await asyncio.open_unix_connection(url.path)
        elif url.scheme == "tcp":
            reader, writer = await asyncio.open_connection(url.hostname, url.port)
        else:
            raise AgentError(AgentErrorCode.UNAVAILABLE, f"Unsupported host agent URL scheme: {url.scheme}")
        try:
            writer.write(request)
            await writer.drain()
            return await read_response(reader, command)
        finally:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    async def _call_ssh(self, url: SplitResult, command: str, request: bytes) -> AgentResponse:  # pragma: no cover
        reader = asyncio.StreamReader()
        reader.feed_data(await asyncio.to_thread(self._exchange_ssh, url, request))
        reader.feed_eof()
        return await read_response(reader, command)

    def _exchange_ssh(self, url: SplitResult, request: bytes) -> bytes:  # pragma: no cover
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                url.hostname or "",
                port=url.port or 22,
                username=url.username,
                pkey=paramiko.PKey.from_path(self.ssh_key_file),
                allow_agent=False,
                look_for_keys=False,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
                channel_timeout=self.timeout,
            )
            stdin, stdout, _ = client.exec_command("bitcart-agent", timeout=self.timeout)
            stdin.write(request)
            stdin.channel.shutdown_write()
            return stdout.read()
        finally:
            client.close()
