from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.services.ext.tor import TorService


class OnionHostMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        tor_service = await request.state.dishka_container.get(TorService)
        response = await call_next(request)
        host = request.headers.get("host", "").split(":")[0]
        onion_host = await tor_service.get_data("onion_host", "")
        if onion_host and not tor_service.is_onion(host):
            response.headers["Onion-Location"] = onion_host + request.url.path
        return response
