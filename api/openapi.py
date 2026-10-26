import json
from collections.abc import Collection, Iterator, Mapping, Sequence
from enum import Enum, StrEnum
from typing import Any, NotRequired, TypedDict

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import Response
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from starlette.routing import BaseRoute

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

    Every API route carries exactly one visibility tag, `public` or `private`.
    Private routes are left out of the served spec and only appear in private dumps.

    They should be set after the "group" tag, which is used to group the endpoints
    in the generated documentation and to name their operation ids.

    **Example**

        ```py
        router = APIRouter(prefix="/products", tags=["products", APITag.public])
        ```
    """

    public = "public"
    private = "private"
    users = "users"

    @classmethod
    def metadata(cls) -> list[OpenAPITag]:
        return [
            {
                "name": cls.users,
                "description": ("Endpoints related to user management in Bitcart API."),
            },
        ]


def generate_operation_id(route: APIRoute) -> str:
    tag = next(iter(route.tags), "default")
    if isinstance(tag, Enum):
        tag = tag.value
    return f"{tag}_{route.name}"


VISIBILITY_TAGS = frozenset({APITag.public.value, APITag.private.value})


def iter_api_routes(routes: Sequence[BaseRoute | RouteContext]) -> Iterator[RouteContext]:
    for route in iter_route_contexts(routes):
        if isinstance(route.original_route, APIRoute):
            yield route


def get_group_tag(route: RouteContext) -> str | None:
    tag = next(iter(route.tags), None)
    if isinstance(tag, Enum):
        tag = tag.value
    return None if tag is None or tag in VISIBILITY_TAGS else tag


def get_visibility_tags(route: RouteContext) -> set[str]:
    return {str(tag) for tag in route.tags if tag in VISIBILITY_TAGS}


def is_private_route(route: RouteContext) -> bool:
    return isinstance(route.original_route, APIRoute) and APITag.private in route.tags


def iter_operations(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for section in ("paths", "webhooks"):
        for path_item in schema.get(section, {}).values():
            yield from path_item.values()


def strip_visibility_tags(schema: dict[str, Any]) -> None:
    used_tags: set[str] = set()
    for operation in iter_operations(schema):
        if "tags" in operation:
            operation["tags"] = [tag for tag in operation["tags"] if tag not in VISIBILITY_TAGS]
            if not operation["tags"]:
                del operation["tags"]
            used_tags.update(operation.get("tags", []))
    if "tags" in schema:
        schema["tags"] = [tag for tag in schema["tags"] if tag["name"] in used_tags]
        if not schema["tags"]:
            del schema["tags"]


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


OPENAPI_URL = "/openapi.json"


# This is required to keep same format on live endpoint and the dumped openapi schema
def dump_openapi(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def set_openapi_route(app: FastAPI) -> None:
    @app.get(OPENAPI_URL, include_in_schema=False)
    async def openapi_json(req: Request) -> Response:
        return Response(dump_openapi(app.openapi()), media_type="application/json")

    app.openapi_url = OPENAPI_URL


def get_openapi_schema(
    app: FastAPI, routes: Sequence[BaseRoute | RouteContext] | None = None, *, include_private: bool = False
) -> dict[str, Any]:
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=[
            route
            for route in iter_route_contexts(app.routes if routes is None else routes)
            if include_private or not is_private_route(route)
        ],
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        separate_input_output_schemas=app.separate_input_output_schemas,
    )
    # for plugins to add custom scopes
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    for name in ("Bearer", "BearerOptional"):
        if name in security_schemes:
            security_schemes[name]["flows"]["password"]["scopes"] = get_all_scopes()
    strip_visibility_tags(schema)
    return schema


def set_openapi_generator(app: FastAPI, settings: Settings) -> None:
    def _openapi_generator() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        if settings.OPENAPI_PATH:
            with log_errors(logger), open(settings.OPENAPI_PATH) as f:
                app.openapi_schema = json.loads(f.read())

        app.openapi_schema = get_openapi_schema(app)
        return app.openapi_schema

    app.openapi = _openapi_generator  # type: ignore[method-assign]


class DumpError(Exception):
    pass


def check_plugin_route_tags(plugin: str, routes: Sequence[BaseRoute], core_routes: Sequence[BaseRoute]) -> None:
    core_groups = {get_group_tag(route) for route in iter_api_routes(core_routes)}
    errors = []
    for route in iter_api_routes(routes):
        if not route.include_in_schema:
            continue
        operation = f"{' '.join(sorted(route.methods or ()))} {route.path}"
        group = get_group_tag(route)
        if group is None:
            errors.append(f"{operation} has no group tag")
        elif group in core_groups:
            errors.append(f"{operation} uses core's group tag {group!r}")
        if len(get_visibility_tags(route)) != 1:
            errors.append(f"{operation} must be tagged either {APITag.public} or {APITag.private}")
    if errors:
        raise DumpError(f"Plugin {plugin} has invalid route tags:\n" + "\n".join(errors))


def get_dump_schema(
    app: FastAPI,
    *,
    include_private: bool = False,
    plugin: str | None = None,
    plugin_routes: Mapping[str, Sequence[BaseRoute]] | None = None,
    groups: Collection[str] = (),
) -> dict[str, Any]:
    plugin_routes = plugin_routes or {}
    plugin_route_ids = {id(route) for routes in plugin_routes.values() for route in routes}
    core_routes = [route for route in app.routes if id(route) not in plugin_route_ids]
    routes: Sequence[BaseRoute | RouteContext] = core_routes
    if plugin is not None:
        if plugin not in plugin_routes:
            raise DumpError(f"Plugin {plugin} is not loaded")
        routes = plugin_routes[plugin]
        check_plugin_route_tags(plugin, plugin_routes[plugin], core_routes)
    if groups:
        routes = [route for route in iter_api_routes(routes) if get_group_tag(route) in groups]
    schema = get_openapi_schema(app, routes, include_private=include_private)
    if not schema.get("paths"):
        raise DumpError("No operations to dump")
    schema["info"]["x-bitcart-surface"] = APITag.private.value if include_private else APITag.public.value
    schema["info"]["x-bitcart-plugins"] = [plugin] if plugin else []
    return schema


__all__ = [
    "get_openapi_parameters",
    "APITag",
    "DumpError",
    "dump_openapi",
    "generate_operation_id",
    "get_dump_schema",
    "get_openapi_schema",
    "set_openapi_generator",
    "set_openapi_route",
]
