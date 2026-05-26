import re
import time
from re import Pattern

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.routing import Match, Mount, Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.metrics import (
    http_request_duration_highr_seconds,
    http_request_duration_seconds,
    http_request_size_bytes,
    http_requests_inprogress,
    http_requests_total,
    http_response_size_bytes,
)


def _get_route_name(scope: Scope, routes: list[Route]) -> str | None:
    for route in routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            path = route.path
            merged = {**scope, **child_scope}
            if isinstance(route, Mount) and route.routes:
                child = _get_route_name(merged, route.routes)
                if child is None:
                    return None
                path += child
            return path
    return None


def _resolve_handler(request: Request) -> str | None:
    router = request.app.router
    route_name = _get_route_name(request.scope, router.routes)
    if not route_name and router.redirect_slashes and request.url.path != "/":
        path = request.url.path
        trim = path.endswith("/")
        new_path = path[:-1] if trim else path + "/"
        redirect_scope = {**request.scope, "path": new_path}
        route_name = _get_route_name(redirect_scope, router.routes)
        if route_name is not None:
            route_name = route_name + "/" if trim else route_name[:-1]
    return route_name


def _content_length(headers: Headers) -> int:
    return int(headers.get("content-length") or 0)


class PrometheusMiddleware:
    def __init__(self, app: ASGIApp, excluded_handlers: tuple[str, ...] = ("/metrics",)) -> None:
        self.app = app
        self.excluded_handlers: list[Pattern[str]] = [re.compile(p) for p in excluded_handlers]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        request = Request(scope)
        handler = _resolve_handler(request)
        if handler is None or any(p.search(handler) for p in self.excluded_handlers):
            return await self.app(scope, receive, send)

        method = request.method
        status = 500
        response_headers: list[tuple[bytes, bytes]] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_headers
            if message["type"] == "http.response.start":
                status = int(message["status"])
                response_headers = message.get("headers", [])
            await send(message)

        http_requests_inprogress.labels(method=method, handler=handler).inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = max(time.perf_counter() - start, 0.0)
            http_requests_inprogress.labels(method=method, handler=handler).dec()
            grouped_status = f"{str(status)[0]}xx"
            http_requests_total.labels(method=method, status=grouped_status, handler=handler).inc()
            http_request_size_bytes.labels(handler=handler).observe(_content_length(request.headers))
            http_response_size_bytes.labels(handler=handler).observe(_content_length(Headers(raw=response_headers)))
            http_request_duration_highr_seconds.observe(duration)
            http_request_duration_seconds.labels(method=method, handler=handler).observe(duration)
