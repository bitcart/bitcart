import structlog
from opentelemetry import trace
from starlette.types import ASGIApp, Receive, Scope, Send

from api.logging import generate_correlation_id


class LogCorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        correlation_id = generate_correlation_id()
        with structlog.contextvars.bound_contextvars(
            correlation_id=correlation_id,
            method=scope["method"],
            path=scope["path"],
        ):
            span = trace.get_current_span()
            span.set_attribute("correlation_id", correlation_id)
            await self.app(scope, receive, send)
