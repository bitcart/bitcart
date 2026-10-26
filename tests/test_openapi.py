import json
from collections.abc import Callable
from enum import Enum
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from starlette.routing import BaseRoute

from api.bootstrap import get_app
from api.openapi import (
    VISIBILITY_TAGS,
    APITag,
    DumpError,
    get_dump_schema,
    get_group_tag,
    get_visibility_tags,
    iter_api_routes,
    iter_operations,
    set_openapi_generator,
)
from api.plugins import BasePlugin, PluginObjects
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.tasks import broker, client_tasks_broker
from api.templates import TemplateManager
from api.types import ClientTasksBroker

QUALITY_BASELINE_PATH = "tests/fixtures/openapi_quality_baseline.json"
HIDDEN_CORE_PATHS = {"/", "/favicon.ico", "/swagger", "/redoc", "/openapi.json"}

private_router = APIRouter()
plugin_router = APIRouter()
plugin_portal_router = APIRouter()


@private_router.get("/items")
async def list_private_items() -> list[str]:
    return []


@plugin_router.get("/items")
async def list_plugin_items() -> list[str]:
    return []


@plugin_portal_router.get("/session")
async def get_portal_session() -> dict[str, str]:
    return {}


type Include = tuple[APIRouter, str, list[str | Enum]]
type PluginSetup = Callable[..., dict[str, list[BaseRoute]]]

PLUGIN_INCLUDES: list[Include] = [
    (plugin_router, "/fixture", ["fixture", APITag.public]),
    (plugin_portal_router, "/fixture/portal", ["fixture_portal", APITag.private]),
]


class FixturePlugin(BasePlugin):
    name = "fixture_plugin"

    def __init__(self, includes: list[Include]) -> None:
        super().__init__("tests")
        self.includes = includes

    def setup_app(self, app: FastAPI) -> None:
        for router, prefix, tags in self.includes:
            app.include_router(router, prefix=prefix, tags=tags)

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def worker_setup(self) -> None:
        pass


@pytest.fixture
def fresh_app(settings: Settings) -> FastAPI:
    fresh_app = get_app(settings)
    set_openapi_generator(fresh_app, settings)
    fresh_app.include_router(private_router, prefix="/hidden", tags=["hidden", APITag.private])
    return fresh_app


@pytest.fixture
def setup_plugin(app: FastAPI, settings: Settings, fresh_app: FastAPI) -> PluginSetup:
    def setup(includes: list[Include] = PLUGIN_INCLUDES) -> dict[str, list[BaseRoute]]:
        plugin = FixturePlugin(includes)
        plugin_registry = PluginRegistry(
            settings,
            broker,
            ClientTasksBroker(client_tasks_broker),
            TemplateManager(),
            PluginObjects({plugin.name: plugin}),
            app.state.dishka_container,
        )
        plugin_registry.setup_app(fresh_app)
        return plugin_registry.plugin_routes

    return setup


def get_operation_ids(schema: dict[str, Any]) -> list[str]:
    return [operation["operationId"] for operation in iter_operations(schema)]


def get_route_operation_ids(routes: list[BaseRoute], *, group: str, visibility: APITag) -> set[str]:
    return {
        route.unique_id
        for route in iter_api_routes(routes)
        if get_group_tag(route) == group and get_visibility_tags(route) == {visibility}
    }


def assert_no_visibility_tags(schema: dict[str, Any]) -> None:
    used_tags = {tag for operation in iter_operations(schema) for tag in operation.get("tags", [])}
    assert not used_tags & VISIBILITY_TAGS
    assert {tag["name"] for tag in schema.get("tags", [])} <= used_tags


def has_response_model(operation: dict[str, Any]) -> bool:
    for status, response in operation["responses"].items():
        if not status.startswith("2"):
            continue
        if "content" not in response or any(
            set(media_type.get("schema", {})) - {"title", "description"} for media_type in response["content"].values()
        ):
            return True
    return False


def get_quality_gaps(schema: dict[str, Any]) -> dict[str, set[str]]:
    gaps: dict[str, set[str]] = {"missing_description": set(), "missing_response_model": set()}
    for operation in iter_operations(schema):
        if not operation.get("description"):
            gaps["missing_description"].add(operation["operationId"])
        if not has_response_model(operation):
            gaps["missing_response_model"].add(operation["operationId"])
    return gaps


def test_core_routes_declare_visibility(app: FastAPI) -> None:
    undeclared = [
        route.path for route in iter_api_routes(app.routes) if route.include_in_schema and len(get_visibility_tags(route)) != 1
    ]
    assert not undeclared


def test_only_non_api_routes_are_hidden(app: FastAPI) -> None:
    hidden = {route.path for route in iter_api_routes(app.routes) if not route.include_in_schema}
    assert hidden == HIDDEN_CORE_PATHS


def test_operation_ids_keep_group_tag(app: FastAPI) -> None:
    for route in iter_api_routes(app.routes):
        if route.include_in_schema:
            assert route.unique_id == f"{get_group_tag(route)}_{route.name}"


def test_served_spec(fresh_app: FastAPI) -> None:
    schema = fresh_app.openapi()
    assert "/hidden/items" not in schema["paths"]
    assert "/invoices" in schema["paths"]
    assert "x-bitcart-surface" not in schema["info"]
    assert "x-bitcart-plugins" not in schema["info"]
    assert_no_visibility_tags(schema)
    assert fresh_app.openapi() is schema


def test_core_dumps(fresh_app: FastAPI, setup_plugin: PluginSetup) -> None:
    plugin_routes = setup_plugin()
    public = get_dump_schema(fresh_app, plugin_routes=plugin_routes)
    private = get_dump_schema(fresh_app, include_private=True, plugin_routes=plugin_routes)
    assert public["info"]["x-bitcart-surface"] == "public"
    assert private["info"]["x-bitcart-surface"] == "private"
    assert public["info"]["x-bitcart-plugins"] == private["info"]["x-bitcart-plugins"] == []
    assert "/hidden/items" not in public["paths"]
    assert "/hidden/items" in private["paths"]
    assert set(private["paths"]) - set(public["paths"]) == {"/hidden/items"}
    for schema in (public, private):
        assert not any(path.startswith("/fixture") for path in schema["paths"])
        assert_no_visibility_tags(schema)


def test_dump_groups(fresh_app: FastAPI) -> None:
    schema = get_dump_schema(fresh_app, include_private=True, groups=["users", "hidden"])
    operation_ids = get_operation_ids(schema)
    assert operation_ids
    assert all(operation_id.startswith(("users_", "hidden_")) for operation_id in operation_ids)
    assert "hidden_list_private_items" in operation_ids
    assert [tag["name"] for tag in schema["tags"]] == ["users"]


def test_dump_without_operations(fresh_app: FastAPI) -> None:
    with pytest.raises(DumpError, match="No operations"):
        get_dump_schema(fresh_app, groups=["hidden"])


def test_core_operation_ids_unique(app: FastAPI) -> None:
    operation_ids = get_operation_ids(get_dump_schema(app, include_private=True))
    assert len(operation_ids) == len(set(operation_ids))


def test_quality_gate_baseline(app: FastAPI) -> None:
    gaps = get_quality_gaps(get_dump_schema(app, include_private=True))
    with open(QUALITY_BASELINE_PATH) as f:
        baseline = json.load(f)
    assert baseline.keys() == gaps.keys()
    for gap, operation_ids in gaps.items():
        new = operation_ids - set(baseline[gap])
        fixed = set(baseline[gap]) - operation_ids
        assert not new, f"New operations with {gap}, fix them instead of adding them to the baseline: {sorted(new)}"
        assert not fixed, f"Remove fixed operations from {gap} in {QUALITY_BASELINE_PATH}: {sorted(fixed)}"


def test_plugin_dump_overlap(app: FastAPI, fresh_app: FastAPI, setup_plugin: PluginSetup) -> None:
    plugin_routes = setup_plugin()
    routes = plugin_routes[FixturePlugin.name]
    core_public = get_dump_schema(app)
    schema = get_dump_schema(
        fresh_app, include_private=True, plugin=FixturePlugin.name, plugin_routes=plugin_routes, groups=["fixture_portal"]
    )
    operation_ids = set(get_operation_ids(schema))
    assert schema["info"]["x-bitcart-surface"] == "private"
    assert schema["info"]["x-bitcart-plugins"] == [FixturePlugin.name]
    assert operation_ids == get_route_operation_ids(routes, group="fixture_portal", visibility=APITag.private)
    assert operation_ids == {"fixture_portal_get_portal_session"}
    assert not operation_ids & set(get_operation_ids(core_public))
    assert_no_visibility_tags(schema)


def test_plugin_public_dump(fresh_app: FastAPI, setup_plugin: PluginSetup) -> None:
    plugin_routes = setup_plugin()
    schema = get_dump_schema(fresh_app, plugin=FixturePlugin.name, plugin_routes=plugin_routes)
    assert set(get_operation_ids(schema)) == {"fixture_list_plugin_items"}
    assert schema["info"]["x-bitcart-surface"] == "public"
    with pytest.raises(DumpError, match="No operations"):
        get_dump_schema(fresh_app, plugin=FixturePlugin.name, plugin_routes=plugin_routes, groups=["fixture_portal"])


def test_plugin_dump_unknown_plugin(fresh_app: FastAPI) -> None:
    with pytest.raises(DumpError, match="not loaded"):
        get_dump_schema(fresh_app, plugin=FixturePlugin.name)


@pytest.mark.parametrize(
    ("tags", "error"),
    [
        ([APITag.public], "has no group tag"),
        (["invoices", APITag.public], "uses core's group tag 'invoices'"),
        (["fixture"], "must be tagged either public or private"),
        (["fixture", APITag.public, APITag.private], "must be tagged either public or private"),
    ],
)
def test_plugin_dump_tag_rules(fresh_app: FastAPI, setup_plugin: PluginSetup, tags: list[str | Enum], error: str) -> None:
    plugin_routes = setup_plugin([(plugin_router, "/fixture", tags)])
    with pytest.raises(DumpError, match=error):
        get_dump_schema(fresh_app, include_private=True, plugin=FixturePlugin.name, plugin_routes=plugin_routes)
