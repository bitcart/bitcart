import json
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api.constants import VERSION
from api.logging import get_logger, log_errors
from api.settings import Environment, Settings
from api.utils.authorization import get_all_scopes

logger = get_logger(__name__)


class OpenAPIExternalDoc(TypedDict):
    description: NotRequired[str]
    url: str


class OpenAPITag(TypedDict):
    name: str
    description: NotRequired[str]
    externalDocs: NotRequired[dict[str, str]]


class APITag(StrEnum):
    """
    Tags used by our documentation to better organize the endpoints.

    They should be set after the "group" tag, which is used to group the endpoints
    in the generated documentation.

    **Example**

        ```py
        router = APIRouter(prefix="/products", tags=["products", APITag.featured])
        ```
    """

    users = "users"

    @classmethod
    def metadata(cls) -> list[OpenAPITag]:
        return [
            {
                "name": cls.users,
                "description": ("Endpoints related to user management in Bitcart API."),
            },
        ]


class OpenAPIParameters(TypedDict):
    title: str
    summary: str
    version: str
    description: str
    docs_url: str | None
    redoc_url: str | None
    openapi_tags: list[dict[str, Any]]
    servers: list[dict[str, Any]] | None


def get_openapi_parameters(settings: Settings) -> OpenAPIParameters:
    current_server = settings.ROOT_PATH or "/"
    return {
        "title": settings.API_TITLE,
        "summary": "Bitcart Merchants API",
        "version": VERSION,
        "description": "Read the docs at https://docs.bitcart.ai",
        "docs_url": None,
        "redoc_url": None,
        "openapi_tags": APITag.metadata(),  # type: ignore
        "swagger_ui_parameters": {
            "docExpansion": "none",
        },
        "servers": [
            {
                "url": current_server,
                "description": "Current instance",
            },
            {
                "url": "https://api.bitcart.ai",
                "description": "Bitcart production demo",
            },
            {
                "url": "https://testnet.bitcart.ai/api",
                "description": "Bitcart testnet demo",
            },
        ]
        if settings.is_environment({Environment.sandbox, Environment.production})
        else [{"url": current_server, "description": "Development environment"}],
    }


def set_openapi_generator(app: FastAPI, settings: Settings) -> None:
    def _openapi_generator() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        if settings.OPENAPI_PATH:
            with log_errors(logger), open(settings.OPENAPI_PATH) as f:
                app.openapi_schema = json.loads(f.read())

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            routes=app.routes,
            webhooks=app.webhooks.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            separate_input_output_schemas=app.separate_input_output_schemas,
        )
        # for plugins to add custom scopes
        schema["components"]["securitySchemes"]["Bearer"]["flows"]["password"]["scopes"] = get_all_scopes()
        schema["components"]["securitySchemes"]["BearerOptional"]["flows"]["password"]["scopes"] = get_all_scopes()
        app.openapi_schema = schema
        return schema

    app.openapi = _openapi_generator  # type: ignore[method-assign]


__all__ = [
    "get_openapi_parameters",
    "APITag",
    "set_openapi_generator",
]
