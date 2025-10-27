import asyncio
import contextlib
import sys
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import structlog
from advanced_alchemy.exceptions import AdvancedAlchemyError, NotFoundError
from dishka.integrations.taskiq import setup_dishka as taskiq_setup_dishka
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy.exc import IntegrityError
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from api.db import AsyncSession
from api.ioc import build_container, setup_dishka
from api.ioc.services import ServicesProvider
from api.logfire import (
    configure_logfire,
    instrument_fastapi,
)
from api.logging import configure as configure_logging
from api.logging import generate_correlation_id, get_logger
from api.openapi import get_openapi_parameters, set_openapi_generator
from api.sentry import configure_sentry
from api.services.ext.tor import TorService
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.tasks import broker, client_tasks_broker
from api.utils.common import excepthook_handler, handle_event_loop_exception
from api.views import router
from worker import start_broker_basic

logger = get_logger("api")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    sys.excepthook = excepthook_handler(logger, sys.excepthook)
    asyncio.get_running_loop().set_exception_handler(
        lambda *args, **kwargs: handle_event_loop_exception(logger, *args, **kwargs)
    )
    await app.state.broker.startup()
    broker_task = asyncio.create_task(start_broker_basic(app.state.client_broker))
    plugin_registry = await app.state.dishka_container.get(PluginRegistry)
    plugin_registry.setup_app(app)
    await plugin_registry.startup()
    for service in ServicesProvider.TO_PRELOAD:
        await app.state.dishka_container.get(service)
    yield
    await plugin_registry.shutdown()
    broker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await broker_task
    await app.state.dishka_container.close()


class LogCorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        structlog.contextvars.bind_contextvars(
            correlation_id=generate_correlation_id(),
            method=scope["method"],
            path=scope["path"],
        )
        await self.app(scope, receive, send)
        structlog.contextvars.unbind_contextvars("correlation_id", "method", "path")


# TODO: remove when https://github.com/fastapi/fastapi/pull/11160 is merged
def patch_call(instance: FastAPI) -> None:
    class _(type(instance)):  # type: ignore[misc]
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


def with_db_rollback(
    handler: Callable[[Request, Any], Awaitable[JSONResponse]],
) -> Callable[[Request, Any], Awaitable[JSONResponse]]:
    """Decorator that ensures database session is rolled back before returning from exception handler.

    This is necessary because when an exception handler catches an exception and returns a response,
    the exception doesn't propagate to dishka's context manager. Without rollback, dishka will try
    to commit the session, which may be in a bad state, causing PendingRollbackError.
    """

    async def wrapper(request: Request, exc: Any) -> JSONResponse:
        session = await request.state.dishka_container.get(AsyncSession)
        await session.rollback()
        return await handler(request, exc)

    return wrapper


@with_db_rollback
async def db_exception_handler(request: Request, exc: AdvancedAlchemyError) -> JSONResponse:
    logger.error("Database error", exc_info=exc)
    return JSONResponse(
        status_code=422,
        content={"error": "Database error", "detail": exc.detail},
    )


@with_db_rollback
async def db_integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "Database error", "detail": str(exc.orig)},
    )


@with_db_rollback
async def db_not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": str(exc)},
    )


exception_handlers: dict[type[Exception], Callable[[Request, Any], Awaitable[JSONResponse]]] = {
    IntegrityError: db_integrity_error_handler,
    NotFoundError: db_not_found_error_handler,
    AdvancedAlchemyError: db_exception_handler,
}


def add_exception_handlers(app: FastAPI) -> None:
    for exc_type, handler in exception_handlers.items():
        app.add_exception_handler(exc_type, handler)

    @app.exception_handler(500)
    async def exception_handler(request: Request, exc: Exception) -> Response:
        # this happens when exception is during container finalization
        # as it is rare enough, we must log it
        if type(exc) in exception_handlers:
            return await exception_handlers[type(exc)](request, exc)
        logger.error(traceback.format_exc())
        return PlainTextResponse("Internal Server Error", status_code=500)


def get_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan, root_path=settings.ROOT_PATH, root_path_in_servers=False, **get_openapi_parameters(settings)
    )

    @app.get("/", include_in_schema=False)
    async def scalar_html(req: Request) -> Any:
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + app.openapi_url
        return get_scalar_api_reference(
            openapi_url=openapi_url,
            title=app.title,
            servers=list(reversed(app.servers)),
            scalar_favicon_url="/favicon.ico",
            dark_mode=False,
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Any:
        return FileResponse("static/favicon.ico")

    @app.get("/swagger", include_in_schema=False)
    async def swagger_docs(req: Request) -> HTMLResponse:
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + app.openapi_url
        return get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_favicon_url="/favicon.ico",
            swagger_ui_parameters=app.swagger_ui_parameters,
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_docs(req: Request) -> HTMLResponse:
        root_path = req.scope.get("root_path", "").rstrip("/")
        openapi_url = root_path + app.openapi_url
        return get_redoc_html(
            openapi_url=openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_favicon_url="/favicon.ico",
        )

    @app.middleware("http")
    async def add_onion_host(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        tor_service = await request.state.dishka_container.get(TorService)
        response = await call_next(request)
        host = request.headers.get("host", "").split(":")[0]
        onion_host = await tor_service.get_data("onion_host", "")
        if onion_host and not tor_service.is_onion(host):
            response.headers["Onion-Location"] = onion_host + request.url.path
        return response

    app.add_middleware(LogCorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    patch_call(app)
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
    app.mount("/images", StaticFiles(directory=settings.images_dir), name="images")
    app.mount("/files/localstorage", StaticFiles(directory=settings.files_dir), name="files")
    add_exception_handlers(app)
    app.include_router(router)
    return app


def configure_production_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings=settings, logfire=True)
    configure_logfire(settings, "server")
    container = build_container(settings)
    configure_sentry(settings)
    app = get_app(settings)
    app.state.broker = broker
    app.state.client_broker = client_tasks_broker
    setup_dishka(container=container, app=app)
    taskiq_setup_dishka(container=container, broker=client_tasks_broker)
    set_openapi_generator(app, settings)
    instrument_fastapi(settings, app)
    return app


if __name__ == "__main__":
    app = configure_production_app()
