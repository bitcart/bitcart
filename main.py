import traceback

from fastapi import FastAPI, Request
from fastapi.requests import HTTPConnection
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles

from api import settings, utils
from api.constants import VERSION
from api.ext import tor as tor_ext
from api.logger import get_logger
from api.settings import Settings
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
        token = settings.settings_ctx.set(request.app.settings)
        try:
            await self.app(scope, receive, send)
        finally:
            settings.settings_ctx.reset(token)


def get_app():
    settings = Settings()
    app = FastAPI(title="BitcartCC", version=VERSION, docs_url="/", redoc_url="/redoc", root_path=settings.root_path)
    app.settings = settings
    app.mount("/images", StaticFiles(directory=settings.images_dir), name="images")
    app.include_router(router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def add_onion_host(request: Request, call_next):
        response = await call_next(request)
        async with utils.redis.wait_for_redis():
            host = request.headers.get("host", "").split(":")[0]
            onion_host = await tor_ext.get_data("onion_host", "")
            if onion_host and not tor_ext.is_onion(host):
                response.headers["Onion-Location"] = onion_host + request.url.path
            return response

    @app.on_event("startup")
    async def startup():
        await app.settings.init()

    @app.on_event("shutdown")
    async def shutdown():
        await app.settings.shutdown()

    @app.exception_handler(500)
    async def exception_handler(request, exc):
        logger.error(traceback.format_exc())
        return PlainTextResponse("Internal Server Error", status_code=500)

    app.add_middleware(RawContextMiddleware)
    return app


app = get_app()
