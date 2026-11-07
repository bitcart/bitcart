import asyncio
import json
import struct
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from api.exceptions import RendererUnavailableError
from api.ext.moneyformat import currency_table
from api.settings import Settings

MAX_REQUEST_BYTES = 1024 * 1024
MAX_REPLY_BYTES = 8 * 1024 * 1024
LENGTH_PREFIX = struct.Struct(">I")


class RenderFailureKind(StrEnum):
    SYNTAX = "syntax"
    FUEL = "fuel"
    OUTPUT = "output"
    RUNTIME = "runtime"
    REQUEST = "request"
    MEMORY = "memory"
    TIMEOUT = "timeout"
    CONTEXT = "context"
    CRASHED = "crashed"
    INVALID_REPLY = "invalid_reply"
    UNAVAILABLE = "unavailable"

    @property
    def is_environment(self) -> bool:
        return self not in {
            RenderFailureKind.SYNTAX,
            RenderFailureKind.FUEL,
            RenderFailureKind.OUTPUT,
            RenderFailureKind.RUNTIME,
        }


class RenderFailure(BaseModel):
    kind: RenderFailureKind
    line: int | None = None
    message: str


class MetadataWrite(BaseModel):
    ref: str
    op: Literal["set", "delete"]
    key: str
    value: Any = None


class RendererReply(BaseModel):
    ok: bool
    text: str = ""
    writes: list[MetadataWrite] = []
    error: RenderFailure | None = None

    @property
    def failure(self) -> RenderFailure:
        return self.error or RenderFailure(kind=RenderFailureKind.INVALID_REPLY, message="renderer reply has no error")

    @classmethod
    def failed(cls, kind: RenderFailureKind, message: str) -> "RendererReply":
        return cls(ok=False, error=RenderFailure(kind=kind, message=message))


class RendererClient:
    def __init__(self, settings: Settings) -> None:
        self.socket_path = settings.RENDERER_SOCKET
        self.timeout = settings.RENDERER_TIMEOUT

    async def render(
        self,
        text: str,
        context: dict[str, Any],
        *,
        autoescape: bool = False,
        safe_key: str | None = None,
        max_wait: float | None = None,
    ) -> RendererReply:
        payload = {
            "text": text,
            "context": context,
            "autoescape": autoescape,
            "safe_key": safe_key,
            "currencies": currency_table.divisibilities,
        }
        return await self._call(payload, max_wait)

    async def check(self, text: str) -> RendererReply:
        return await self._call({"text": text, "check": True})

    async def _call(self, payload: dict[str, Any], max_wait: float | None = None) -> RendererReply:
        body = json.dumps(payload).encode()
        if len(body) > MAX_REQUEST_BYTES:
            return RendererReply.failed(RenderFailureKind.CONTEXT, "template data is too large")
        try:
            async with asyncio.timeout(self.timeout if max_wait is None else max_wait):
                return await self._exchange(body)
        except TimeoutError as e:
            raise RendererUnavailableError("renderer did not answer in time") from e
        except OSError as e:
            raise RendererUnavailableError(f"renderer connection failed: {e}") from e

    async def _exchange(self, body: bytes) -> RendererReply:
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        try:
            writer.write(LENGTH_PREFIX.pack(len(body)) + body)
            await writer.drain()
            prefix = await reader.readexactly(LENGTH_PREFIX.size)
            size = LENGTH_PREFIX.unpack(prefix)[0]
            if size > MAX_REPLY_BYTES:
                return RendererReply.failed(RenderFailureKind.INVALID_REPLY, "renderer reply is too large")
            return RendererReply.model_validate_json(await reader.readexactly(size))
        except asyncio.IncompleteReadError:
            return RendererReply.failed(RenderFailureKind.CRASHED, "renderer worker stopped during the render")
        except ValidationError:
            return RendererReply.failed(RenderFailureKind.INVALID_REPLY, "renderer reply is malformed")
        finally:
            writer.close()
