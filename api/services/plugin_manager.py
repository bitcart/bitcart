import json
import os
import shutil
import tempfile
from typing import Any, cast

import aiofiles
from dishka import AsyncContainer, Scope
from fastapi import HTTPException, UploadFile
from jsonschema import validate
from packaging.requirements import Requirement

from api import constants, utils
from api.constants import VERSION
from api.schemas.policies import PluginsState
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings


class PluginManager:
    def __init__(self, settings: Settings, plugin_registry: PluginRegistry, container: AsyncContainer) -> None:
        self.settings = settings
        self.plugin_registry = plugin_registry
        self.container = container
        self.plugins_schema: dict[str, Any] = {}

    async def fetch_schema(self) -> None:
        schema_path = os.path.join(self.settings.DATADIR, "plugins_schema.json")
        if os.path.exists(schema_path):
            async with aiofiles.open(schema_path) as f:
                plugins_schema = json.loads(await f.read())
            if plugins_schema["$id"] == constants.PLUGINS_SCHEMA_URL:
                self.plugins_schema = plugins_schema
                return
        self.plugins_schema = await utils.common.send_request("GET", constants.PLUGINS_SCHEMA_URL)
        async with aiofiles.open(schema_path, "w") as f:
            await f.write(json.dumps(self.plugins_schema))

    async def start(self) -> None:
        await self.fetch_schema()

    def get_plugins(self) -> list[dict[str, Any]]:
        plugins = []
        for author in os.listdir(self.settings.plugins_dir):
            if not os.path.isdir(os.path.join(self.settings.plugins_dir, author)):
                continue
            for plugin in os.listdir(os.path.join(self.settings.plugins_dir, author)):
                manifest_path = os.path.join(self.settings.plugins_dir, author, plugin, "manifest.json")
                if not os.path.exists(manifest_path):
                    continue
                with open(manifest_path) as f:
                    manifest = f.read()
                try:
                    plugins.append(self.parse_manifest(manifest))
                except ValueError:
                    continue
        return plugins

    def parse_manifest(self, manifest_str: str) -> dict[str, Any]:
        try:
            manifest = cast(dict[str, Any], json.loads(manifest_str))
        except json.JSONDecodeError as e:
            raise ValueError("Invalid manifest.json: invalid JSON") from e
        try:
            validate(manifest, schema=self.plugins_schema)
        except Exception as e:
            raise ValueError(f"Invalid manifest.json: {e}") from e
        # validate version constraints
        version_constraint = manifest["constraints"]["bitcart"]
        req = Requirement(f"bitcart{version_constraint}")
        if VERSION not in req.specifier:
            raise ValueError(
                f"Invalid manifest.json: plugin requires Bitcart version{version_constraint}, but current version is {VERSION}"
            )
        return manifest

    def get_moved_name(self, manifest: dict[str, Any], install: dict[str, Any]) -> str:
        variants = {
            "backend": self.settings.BACKEND_PLUGINS_DIR,
            "admin": self.settings.ADMIN_PLUGINS_DIR,
            "store": self.settings.STORE_PLUGINS_DIR,
            "daemon": self.settings.DAEMON_PLUGINS_DIR,
            "docker": self.settings.DOCKER_PLUGINS_DIR,
        }
        org_name = manifest["author"].lower()
        if install["type"] in ("admin", "store"):
            org_name = "@" + org_name
        if install["type"] == "docker":
            return os.path.join(variants[install["type"]], org_name + "_" + os.path.basename(install["path"]))
        return os.path.join(variants[install["type"]], org_name, os.path.basename(install["path"]))

    def process_installation_hooks(self, path: str, manifest: dict[str, Any]) -> None:
        for install in manifest["installs"]:
            moved_name = self.get_moved_name(manifest, install)
            dest_parent = os.path.dirname(moved_name)
            os.makedirs(dest_parent, exist_ok=True)
            if install["type"] == "backend":
                init_file = os.path.join(dest_parent, "__init__.py")
                if not os.path.exists(init_file):
                    with open(init_file, "w"):
                        pass
            if os.path.exists(moved_name):
                utils.files.remove_tree(moved_name)
            shutil.move(os.path.join(path, install["path"]), moved_name)

    def uninstall_plugin(self, author: str, name: str) -> None:
        plugin_path = os.path.join(self.settings.plugins_dir, author.lower(), name.lower())
        manifest_path = os.path.join(plugin_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return
        with open(manifest_path) as f:
            manifest_str = f.read()
        manifest = self.parse_manifest(manifest_str)
        backend_org_dirs: set[str] = set()
        for install in manifest["installs"]:
            path = self.get_moved_name(manifest, install)
            if os.path.exists(path):
                utils.files.remove_tree(path)
            if install["type"] == "backend":
                backend_org_dirs.add(os.path.dirname(path))
        utils.files.remove_tree(plugin_path)
        for org_dir in backend_org_dirs:
            try:
                entries = os.listdir(org_dir) if os.path.isdir(org_dir) else []
            except FileNotFoundError:
                entries = []
            has_plugin_dirs = any(os.path.isdir(os.path.join(org_dir, entry)) and entry != "__pycache__" for entry in entries)
            if not has_plugin_dirs:
                init_file = os.path.join(org_dir, "__init__.py")
                if os.path.exists(init_file):
                    os.remove(init_file)
                pycache_dir = os.path.join(org_dir, "__pycache__")
                if os.path.isdir(pycache_dir):
                    utils.files.remove_tree(pycache_dir)

    def get_installed_plugins(self) -> dict[str, Any]:
        failed_path = os.path.join(self.settings.DATADIR, ".plugins-failed")
        is_error = os.path.exists(failed_path)
        return {"success": not is_error, "plugins": self.get_plugins()}

    async def install_plugin(self, plugin: UploadFile) -> dict[str, Any]:
        filename = cast(str, plugin.filename)
        if not filename.endswith(".bitcart"):
            return {"status": "error", "message": "Invalid file extension"}
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, filename)
        async with aiofiles.open(path, "wb") as f:
            await f.write(await plugin.read())
        plugin_path = os.path.join(temp_dir, "plugin")
        shutil.unpack_archive(path, plugin_path, "zip")
        manifest_path = os.path.join(plugin_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return {"status": "error", "message": "Invalid plugin archive: missing manifest.json"}
        async with aiofiles.open(manifest_path) as f:
            manifest_str = await f.read()
        try:
            manifest = self.parse_manifest(manifest_str)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        final_path = os.path.join(
            self.settings.plugins_dir, os.path.join(manifest["author"].lower(), manifest["name"].lower())
        )
        if os.path.exists(final_path):
            utils.files.remove_tree(final_path)
        shutil.move(plugin_path, final_path)
        self.process_installation_hooks(final_path, manifest)
        return {
            "status": "success",
            "message": "Successfully installed plugin files. Restart your instance for plugin to load",
        }

    async def add_license(self, license_key: str) -> dict[str, Any]:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            state = await setting_service.get_setting(PluginsState)
            license_keys = state.license_keys
            if license_key in license_keys:
                raise HTTPException(status_code=400, detail="License key already added")
            try:
                license_info = await utils.common.send_request(
                    "GET", f"{self.settings.LICENSE_SERVER_URL}/licenses/{license_key}", return_json=False
                )
                if license_info[0].status != 200:
                    raise HTTPException(status_code=400, detail="Invalid license key")
                license_info = await license_info[0].json()
                license_keys[license_key] = license_info
                state = PluginsState(**state.model_dump(exclude={"license_keys"}), license_keys=license_keys)
                await setting_service.set_setting(state)
                await self.plugin_registry.run_hook("license_changed", license_key, license_info)
                return license_info
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid license key: {str(e)}") from None

    async def get_licenses(self) -> list[dict[str, Any]]:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            state = await setting_service.get_setting(PluginsState)
            return list(state.license_keys.values())

    async def delete_license(self, license_key: str) -> bool:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            state = await setting_service.get_setting(PluginsState)
            license_info = state.license_keys.get(license_key)
            state.license_keys.pop(license_key, None)
            await setting_service.set_setting(state)
            if license_info:
                await self.plugin_registry.run_hook("license_changed", None, license_info)
            return True
