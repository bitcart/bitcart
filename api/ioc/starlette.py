from collections.abc import Awaitable, Callable

from dishka import AsyncContainer
from dishka import Scope as DIScope
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket


class HTTPContainerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        context = {Request: request}
        di_scope = DIScope.REQUEST
        async with request.app.state.dishka_container(
            context,
            scope=di_scope,
        ) as request_container:
            request.state.dishka_container = request_container
            return await call_next(request)


class WebSocketContainerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "websocket":
            return await self.app(scope, receive, send)
        request = WebSocket(scope, receive, send)
        context = {WebSocket: request}
        di_scope = DIScope.SESSION
        async with request.app.state.dishka_container(
            context,
            scope=di_scope,
        ) as request_container:
            request.state.dishka_container = request_container
            return await self.app(scope, receive, send)


def setup_dishka(container: AsyncContainer, app: FastAPI) -> None:
    app.add_middleware(HTTPContainerMiddleware)
    app.add_middleware(WebSocketContainerMiddleware)
    app.state.dishka_container = container
