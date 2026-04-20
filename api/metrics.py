import re
import time
from re import Pattern

from prometheus_client import Counter, Gauge, Histogram, Summary
from starlette.routing import BaseRoute, Match, Mount
from starlette.types import ASGIApp, Message, Receive, Scope, Send

NAMESPACE = "bitcart"

pending_creation_payment_methods_count = Gauge(
    "bitcart_pending_creation_payment_methods_count",
    "Number of payment methods pending creation",
    labelnames=["currency", "contract", "store", "lightning"],
    multiprocess_mode="livesum",
)

_HIGHR_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
    7.5,
    10.0,
    30.0,
    60.0,
    float("inf"),
)
_LOWR_BUCKETS = (0.1, 0.5, 1.0, float("inf"))

_http_requests_total = Counter(
    "http_requests_total",
    "Total number of requests by method, status and handler.",
    labelnames=("method", "status", "handler"),
    namespace=NAMESPACE,
)
_http_request_size_bytes = Summary(
    "http_request_size_bytes",
    "Content length of incoming requests by handler.",
    labelnames=("handler",),
    namespace=NAMESPACE,
)
_http_response_size_bytes = Summary(
    "http_response_size_bytes",
    "Content length of outgoing responses by handler.",
    labelnames=("handler",),
    namespace=NAMESPACE,
)
_http_request_duration_highr_seconds = Histogram(
    "http_request_duration_highr_seconds",
    "Latency with many buckets but no API specific labels.",
    buckets=_HIGHR_BUCKETS,
    namespace=NAMESPACE,
)
_http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latency with only few buckets by handler.",
    labelnames=("method", "handler"),
    buckets=_LOWR_BUCKETS,
    namespace=NAMESPACE,
)
_http_requests_inprogress = Gauge(
    "http_requests_inprogress",
    "Number of HTTP requests in progress.",
    labelnames=("method", "handler"),
    namespace=NAMESPACE,
    multiprocess_mode="livesum",
)


def _get_route_name(scope: Scope, routes: list[BaseRoute]) -> str | None:
    for route in routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            path: str | None = getattr(route, "path", None)
            merged = {**scope, **child_scope}
            if isinstance(route, Mount) and route.routes:
                child = _get_route_name(merged, route.routes)
                if child is None:
                    return None
                path = (path or "") + child
            return path
    return None


def _resolve_handler(scope: Scope) -> str | None:
    app = scope.get("app")
    router = getattr(app, "router", None)
    if router is None:
        return None
    route_name = _get_route_name(scope, router.routes)
    if route_name is None and getattr(router, "redirect_slashes", False) and scope.get("path") != "/":
        redirect_scope = dict(scope)
        original_path = scope["path"]
        if original_path.endswith("/"):
            redirect_scope["path"] = original_path[:-1]
            trim = True
        else:
            redirect_scope["path"] = original_path + "/"
            trim = False
        route_name = _get_route_name(redirect_scope, router.routes)
        if route_name is not None:
            route_name = route_name + "/" if trim else route_name[:-1]
    return route_name


def _content_length(headers: list[tuple[bytes, bytes]]) -> int:
    for name, value in headers:
        if name.lower() == b"content-length":
            try:
                return int(value.decode("latin-1"))
            except (ValueError, UnicodeDecodeError):
                return 0
    return 0


class PrometheusMiddleware:
    def __init__(self, app: ASGIApp, excluded_handlers: tuple[str, ...] = ("/metrics",)) -> None:
        self.app = app
        self.excluded_handlers: list[Pattern[str]] = [re.compile(p) for p in excluded_handlers]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        handler = _resolve_handler(scope)
        if handler is None or any(p.search(handler) for p in self.excluded_handlers):
            return await self.app(scope, receive, send)

        method = scope["method"]
        status = 500
        response_headers: list[tuple[bytes, bytes]] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_headers
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = message.get("headers", [])
            await send(message)

        _http_requests_inprogress.labels(method=method, handler=handler).inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = max(time.perf_counter() - start, 0.0)
            _http_requests_inprogress.labels(method=method, handler=handler).dec()
            grouped_status = f"{str(status)[0]}xx"
            _http_requests_total.labels(method=method, status=grouped_status, handler=handler).inc()
            _http_request_duration_highr_seconds.observe(duration)
            _http_request_duration_seconds.labels(method=method, handler=handler).observe(duration)
            _http_request_size_bytes.labels(handler=handler).observe(_content_length(scope.get("headers", [])))
            _http_response_size_bytes.labels(handler=handler).observe(_content_length(response_headers))
