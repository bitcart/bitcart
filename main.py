import json
import traceback
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.requests import HTTPConnection
from fastapi.responses import HTMLResponse
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from api import settings as settings_module
from api import utils
from api.constants import VERSION
from api.ext import tor as tor_ext
from api.logger import get_logger
from api.settings import Settings
from api.utils.logging import log_errors
from api.views import router

logger = get_logger(__name__)


class RawContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = HTTPConnection(scope, receive)
        token = settings_module.settings_ctx.set(request.app.settings)
        try:
            await self.app(scope, receive, send)
        finally:
            settings_module.settings_ctx.reset(token)


# TODO: remove when https://github.com/fastapi/fastapi/pull/11160 is merged
def patch_call(instance):
    class _(type(instance)):
        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if self.root_path:
                root_path = scope.get("root_path", "")
                if root_path and self.root_path != root_path:
                    logger.warning(
                        f"The ASGI server is using a different root path than the one "
                        f"configured in FastAPI. The configured root path is: "
                        f"{self.root_path}, the ASGI server root path is: {root_path}. "
                        f"The former will be used."
                    )
                scope["root_path"] = self.root_path
                path = scope.get("path")
                if path and not path.startswith(self.root_path):
                    scope["path"] = self.root_path + path
                raw_path: bytes | None = scope.get("raw_path")
                if raw_path and not raw_path.startswith(self.root_path.encode()):
                    scope["raw_path"] = self.root_path.encode() + raw_path
            await Starlette.__call__(self, scope, receive, send)

    instance.__class__ = _


def get_app():
    settings = Settings()

    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=1.0,
            _experiments={
                "continuous_profiling_auto_start": True,
            },
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.ctx_token = settings_module.settings_ctx.set(app.settings)  # for events context
        await settings.init()
        await settings.plugins.startup()
        yield
        await app.settings.shutdown()
        await settings.plugins.shutdown()
        settings_module.settings_ctx.reset(app.ctx_token)

    app = FastAPI(
        title=settings.api_title,
        version=VERSION,
        redoc_url=None,
        docs_url=None,
        root_path=settings.root_path,
        description="Bitcart Merchants API",
        lifespan=lifespan,
    )

    async def swagger_docs(req: Request) -> HTMLResponse:
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + app.openapi_url
        return get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_favicon_url="/static/favicon.ico",
        )

    async def redoc_docs(req: Request) -> HTMLResponse:
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + app.openapi_url
        return get_redoc_html(
            openapi_url=openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_favicon_url="/static/favicon.ico",
        )

    app.add_api_route("/swagger", swagger_docs, include_in_schema=False)
    app.add_api_route("/", redoc_docs, include_in_schema=False)
    patch_call(app)
    app.settings = settings
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    app.mount("/images", StaticFiles(directory=settings.images_dir), name="images")
    app.mount("/files/localstorage", StaticFiles(directory=settings.files_dir), name="files")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    settings.init_logging()
    settings.load_plugins()

    settings.plugins.setup_app(app)
    # include built-in routes later to allow plugins to override them
    app.include_router(router)

    @app.middleware("http")
    async def add_onion_host(request: Request, call_next):
        response = await call_next(request)
        async with utils.redis.wait_for_redis():
            host = request.headers.get("host", "").split(":")[0]
            onion_host = await tor_ext.get_data("onion_host", "")
            if onion_host and not tor_ext.is_onion(host):
                response.headers["Onion-Location"] = onion_host + request.url.path
            return response

    @app.exception_handler(500)
    async def exception_handler(request, exc):
        logger.error(traceback.format_exc())
        return PlainTextResponse("Internal Server Error", status_code=500)

    app.add_middleware(RawContextMiddleware)

    if settings.openapi_path:
        with log_errors(), open(settings.openapi_path) as f:
            app.openapi_schema = json.loads(f.read())
    return app


app = get_app()
