from __future__ import annotations

import io
import json
import os
import pathlib
import zipfile
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from dishka import Scope
from fastapi import FastAPI
from sqlalchemy import text

from api.constants import VERSION
from api.db import AsyncEngine
from api.schemas.policies import PluginsState
from api.services.plugin_manager import PluginManager
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings

pytestmark = pytest.mark.anyio

FUTURE_VERSION = "999.0.0.0"


def make_archive(name: str, version: str, constraint: str = "") -> bytes:
    path = f"src/backend/{name.lower()}"
    manifest = {
        "name": name,
        "author": "bitcart",
        "version": version,
        "constraints": {"bitcart": constraint},
        "installs": [{"type": "backend", "path": path}],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(f"{path}/plugin.py", f"VERSION = {version!r}\n")
    return buffer.getvalue()


class FakeMarketplace:
    def __init__(self) -> None:
        self.plugins: dict[str, dict[str, Any]] = {}

    def add(self, name: str, selected: str | None, versions: tuple[str, ...], *, license_key: str | None = None) -> str:
        plugin_id = f"{name}-id"
        self.plugins[plugin_id] = {
            "entry": {"id": plugin_id, "name": name, "author": "bitcart", "plugin_version": selected},
            "archives": {version: make_archive(name, version) for version in versions},
            "license_key": license_key,
        }
        return plugin_id

    async def list_plugins(self, request: web.Request) -> web.Response:
        current = request.query.get("bitcart_version") == VERSION
        return web.json_response(
            [
                plugin["entry"] if current else {**plugin["entry"], "plugin_version": next(iter(plugin["archives"]))}
                for plugin in self.plugins.values()
            ]
        )

    async def download(self, request: web.Request) -> web.Response:
        plugin = self.plugins[request.match_info["plugin_id"]]
        if plugin["license_key"] and request.query.get("license_key") != plugin["license_key"]:
            return web.json_response({"detail": "Invalid license key"}, status=403)
        return web.Response(body=plugin["archives"][request.query.get("version", next(iter(plugin["archives"])))])


@pytest.fixture
def plugin_settings(settings: Settings, tmp_path: pathlib.Path) -> Settings:
    dirs = {
        "DATADIR": "data",
        "BACKEND_PLUGINS_DIR": "backend",
        "ADMIN_PLUGINS_DIR": "admin",
        "STORE_PLUGINS_DIR": "store",
        "DOCKER_PLUGINS_DIR": "docker",
    }
    for name in dirs.values():
        (tmp_path / name).mkdir()
    return settings.model_copy(update={key: str(tmp_path / name) for key, name in dirs.items()})


@pytest.fixture
async def plugin_manager(app: FastAPI, plugin_settings: Settings) -> PluginManager:
    container = app.state.dishka_container
    return PluginManager(plugin_settings, await container.get(PluginRegistry), container)


@pytest.fixture
async def marketplace(plugin_manager: PluginManager) -> AsyncIterator[FakeMarketplace]:
    fake = FakeMarketplace()
    web_app = web.Application()
    web_app.router.add_get("/plugins", fake.list_plugins)
    web_app.router.add_get("/plugins/{plugin_id}/download", fake.download)
    async with TestServer(web_app) as server:
        url = str(server.make_url("")).rstrip("/")
        plugin_manager.settings = plugin_manager.settings.model_copy(update={"LICENSE_SERVER_URL": url})
        yield fake


async def install(
    plugin_manager: PluginManager, tmp_path: pathlib.Path, name: str, version: str, constraint: str = ""
) -> dict[str, Any]:
    path = tmp_path / f"{name}-{version}.bitcart"
    path.write_bytes(make_archive(name, version, constraint))
    return await plugin_manager.install_from_archive(str(path))


def installed_version(settings: Settings, name: str) -> str:
    package = name.lower()
    with open(os.path.join(settings.plugins_dir, "bitcart", package, "manifest.json")) as f:
        manifest_version = json.load(f)["version"]
    with open(os.path.join(settings.BACKEND_PLUGINS_DIR, "bitcart", package, "plugin.py")) as f:
        assert f.read() == f"VERSION = {manifest_version!r}\n"
    return manifest_version


async def store_licenses(app: FastAPI, plugin_id: str, name: str, keys: dict[str, bool]) -> None:
    license_keys = {
        key: {"license_key": key, "plugin_id": plugin_id, "plugin_name": name, "plugin_author": "bitcart", "active": active}
        for key, active in keys.items()
    }
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        setting_service = await container.get(SettingService)
        await setting_service.set_setting(PluginsState(license_keys=license_keys))


async def test_get_plugins_lists_incompatible_plugins(
    plugin_manager: PluginManager, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await install(plugin_manager, tmp_path, "Compatible", "1.0.0")
    await install(plugin_manager, tmp_path, "Outdated", "1.0.0", f"<={VERSION}")
    monkeypatch.setattr("api.services.plugin_manager.VERSION", FUTURE_VERSION)
    plugins = {plugin["name"]: plugin for plugin in plugin_manager.get_plugins()}
    assert plugins["Compatible"]["compatible"] is True
    assert plugins["Compatible"]["incompatible_reason"] is None
    assert plugins["Outdated"]["compatible"] is False
    assert f"<={VERSION}" in plugins["Outdated"]["incompatible_reason"]
    assert FUTURE_VERSION in plugins["Outdated"]["incompatible_reason"]


async def test_uninstall_incompatible_plugin(
    plugin_manager: PluginManager, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await install(plugin_manager, tmp_path, "Outdated", "1.0.0", f"<={VERSION}")
    monkeypatch.setattr("api.services.plugin_manager.VERSION", FUTURE_VERSION)
    plugin_manager.uninstall_plugin("bitcart", "Outdated")
    assert plugin_manager.get_plugins() == []
    assert not os.path.exists(os.path.join(plugin_manager.settings.BACKEND_PLUGINS_DIR, "bitcart", "outdated"))


async def test_install_rejects_incompatible_archive(plugin_manager: PluginManager, tmp_path: pathlib.Path) -> None:
    result = await install(plugin_manager, tmp_path, "Future", "1.0.0", f">={FUTURE_VERSION}")
    assert result["status"] == "error"
    assert f">={FUTURE_VERSION}" in result["message"]
    assert plugin_manager.get_plugins() == []
    assert os.listdir(plugin_manager.settings.BACKEND_PLUGINS_DIR) == []


async def test_update_plugins_installs_selected_versions(
    app: FastAPI, plugin_manager: PluginManager, marketplace: FakeMarketplace, tmp_path: pathlib.Path
) -> None:
    paid_id = marketplace.add("Paid", "1.1.0", ("1.0.0", "1.1.0"), license_key="paid-key")
    marketplace.add("Free", "2.0.0", ("1.0.0", "2.0.0"))
    marketplace.add("Current", "1.0.0", ("1.0.0",))
    marketplace.add("Local", "1.1.0", ("1.1.0",))
    for name in ("Paid", "Free", "Current"):
        await install(plugin_manager, tmp_path, name, "1.0.0")
    await install(plugin_manager, tmp_path, "Manual", "1.0.0")
    await install(plugin_manager, tmp_path, "Local", "2.0.0")
    await store_licenses(app, paid_id, "Paid", {"paid-key": True})
    results = await plugin_manager.update_plugins()
    assert results == {"bitcart/Paid": "updated to 1.1.0", "bitcart/Free": "updated to 2.0.0"}
    settings = plugin_manager.settings
    assert installed_version(settings, "Paid") == "1.1.0"
    assert installed_version(settings, "Free") == "2.0.0"
    assert installed_version(settings, "Current") == "1.0.0"
    assert installed_version(settings, "Manual") == "1.0.0"
    assert installed_version(settings, "Local") == "2.0.0"


async def test_update_plugins_prefers_active_license(
    app: FastAPI, plugin_manager: PluginManager, marketplace: FakeMarketplace, tmp_path: pathlib.Path
) -> None:
    paid_id = marketplace.add("Paid", "1.1.0", ("1.0.0", "1.1.0"), license_key="renewed-key")
    await install(plugin_manager, tmp_path, "Paid", "1.0.0")
    await store_licenses(app, paid_id, "Paid", {"renewed-key": True, "expired-key": False})
    assert await plugin_manager.update_plugins() == {"bitcart/Paid": "updated to 1.1.0"}
    assert installed_version(plugin_manager.settings, "Paid") == "1.1.0"


async def test_update_plugins_before_settings_migrations(
    app: FastAPI, plugin_manager: PluginManager, marketplace: FakeMarketplace, tmp_path: pathlib.Path
) -> None:
    paid_id = marketplace.add("Paid", "1.1.0", ("1.0.0", "1.1.0"), license_key="paid-key")
    await install(plugin_manager, tmp_path, "Paid", "1.0.0")
    await store_licenses(app, paid_id, "Paid", {"paid-key": True})
    engine = await app.state.dishka_container.get(AsyncEngine)
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE settings DROP COLUMN updated"))
    assert await plugin_manager.update_plugins() == {"bitcart/Paid": "updated to 1.1.0"}
    assert installed_version(plugin_manager.settings, "Paid") == "1.1.0"


async def test_update_plugins_failure_keeps_old_version(
    plugin_manager: PluginManager, marketplace: FakeMarketplace, tmp_path: pathlib.Path
) -> None:
    marketplace.add("Unlicensed", "1.1.0", ("1.0.0", "1.1.0"), license_key="paid-key")
    marketplace.add("Free", "2.0.0", ("1.0.0", "2.0.0"))
    marketplace.add("Future", None, ("2.0.0",))
    for name in ("Unlicensed", "Free", "Future"):
        await install(plugin_manager, tmp_path, name, "1.0.0")
    results = await plugin_manager.update_plugins()
    assert "failed: download returned HTTP 403" in results["bitcart/Unlicensed"]
    assert results["bitcart/Free"] == "updated to 2.0.0"
    assert "no version compatible" in results["bitcart/Future"]
    settings = plugin_manager.settings
    assert installed_version(settings, "Unlicensed") == "1.0.0"
    assert installed_version(settings, "Free") == "2.0.0"
    assert installed_version(settings, "Future") == "1.0.0"


async def test_update_plugins_marketplace_unavailable(plugin_manager: PluginManager, tmp_path: pathlib.Path) -> None:
    await install(plugin_manager, tmp_path, "Free", "1.0.0")
    plugin_manager.settings = plugin_manager.settings.model_copy(update={"LICENSE_SERVER_URL": "http://127.0.0.1:9"})
    results = await plugin_manager.update_plugins()
    assert list(results) == ["marketplace"]
    assert installed_version(plugin_manager.settings, "Free") == "1.0.0"


async def test_update_plugins_skips_symlinked_plugins(
    plugin_manager: PluginManager, marketplace: FakeMarketplace, tmp_path: pathlib.Path
) -> None:
    marketplace.add("Dev", "2.0.0", ("1.0.0", "2.0.0"))
    await install(plugin_manager, tmp_path, "Dev", "1.0.0")
    backend_path = os.path.join(plugin_manager.settings.BACKEND_PLUGINS_DIR, "bitcart", "dev")
    source_path = tmp_path / "dev-source"
    os.rename(backend_path, source_path)
    os.symlink(source_path, backend_path)
    assert await plugin_manager.update_plugins() == {}
    assert os.path.islink(backend_path)
    assert installed_version(plugin_manager.settings, "Dev") == "1.0.0"
