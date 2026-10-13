import json
import os
import shutil
import tempfile
from typing import Any, cast

import aiofiles
from aiohttp import ClientSession, ClientTimeout
from dishka import AsyncContainer, Scope
from fastapi import HTTPException, UploadFile
from jsonschema import validate
from packaging.requirements import InvalidRequirement, Requirement  # TODO: drop requirement on packaging
from packaging.version import InvalidVersion, Version

from api import constants, utils
from api.constants import VERSION
from api.logging import get_exception_summary
from api.schemas.policies import PluginsState
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings

MARKETPLACE_TIMEOUT = 120


def is_bitcart_compatible(version_constraint: str, bitcart_version: str) -> bool:
    return bitcart_version in Requirement(f"bitcart{version_constraint}").specifier


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
                    manifest_str = f.read()
                try:
                    manifest = self.parse_manifest(manifest_str)
                except ValueError:
                    continue
                incompatible_reason = self.check_compatibility(manifest)
                plugins.append(
                    {**manifest, "compatible": incompatible_reason is None, "incompatible_reason": incompatible_reason}
                )
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
        try:
            Requirement(f"bitcart{manifest['constraints']['bitcart']}")
        except InvalidRequirement as e:
            raise ValueError("Invalid manifest.json: invalid Bitcart version constraint") from e
        return manifest

    @staticmethod
    def check_compatibility(manifest: dict[str, Any]) -> str | None:
        version_constraint = manifest["constraints"]["bitcart"]
        if is_bitcart_compatible(version_constraint, VERSION):
            return None
        return f"Plugin requires Bitcart version{version_constraint}, but current version is {VERSION}"

    def get_install_dirs(self) -> dict[str, str]:
        return {
            "backend": self.settings.BACKEND_PLUGINS_DIR,
            "admin": self.settings.ADMIN_PLUGINS_DIR,
            "store": self.settings.STORE_PLUGINS_DIR,
            "docker": self.settings.DOCKER_PLUGINS_DIR,
        }

    def get_moved_name(self, manifest: dict[str, Any], install: dict[str, Any]) -> str:
        install_dir = self.get_install_dirs()[install["type"]]
        org_name = manifest["author"].lower()
        if install["type"] in ("admin", "store"):
            org_name = "@" + org_name
        if install["type"] == "docker":
            return os.path.join(install_dir, org_name + "_" + os.path.basename(install["path"]))
        return os.path.join(install_dir, org_name, os.path.basename(install["path"]))

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
        return {"success": not is_error, "bitcart_version": VERSION, "plugins": self.get_plugins()}

    async def install_plugin(self, plugin: UploadFile) -> dict[str, Any]:
        filename = cast(str, plugin.filename)
        if not filename.endswith(".bitcart"):
            return {"status": "error", "message": "Invalid file extension"}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "plugin.bitcart")
            async with aiofiles.open(path, "wb") as f:
                await f.write(await plugin.read())
            return await self.install_from_archive(path)

    async def install_from_archive(self, archive_path: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_path = os.path.join(temp_dir, "plugin")
            shutil.unpack_archive(archive_path, plugin_path, "zip")
            manifest_path = os.path.join(plugin_path, "manifest.json")
            if not os.path.exists(manifest_path):
                return {"status": "error", "message": "Invalid plugin archive: missing manifest.json"}
            async with aiofiles.open(manifest_path) as f:
                manifest_str = await f.read()
            try:
                manifest = self.parse_manifest(manifest_str)
            except ValueError as e:
                return {"status": "error", "message": str(e)}
            if incompatible_reason := self.check_compatibility(manifest):
                return {"status": "error", "message": incompatible_reason}
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

    def is_dev_plugin(self, manifest: dict[str, Any]) -> bool:
        return any(os.path.islink(self.get_moved_name(manifest, install)) for install in manifest["installs"])

    async def update_plugins(self) -> dict[str, str]:
        installed = [plugin for plugin in self.get_plugins() if not self.is_dev_plugin(plugin)]
        if not installed:
            return {}
        licenses = {
            (info["plugin_author"], info["plugin_name"]): info
            for info in sorted(await self.get_licenses(), key=lambda info: bool(info.get("active")))
        }
        results: dict[str, str] = {}
        async with ClientSession(timeout=ClientTimeout(total=MARKETPLACE_TIMEOUT)) as session:
            try:
                async with session.get(
                    f"{self.settings.LICENSE_SERVER_URL}/plugins", params={"bitcart_version": VERSION}
                ) as resp:
                    resp.raise_for_status()
                    marketplace = await resp.json()
            except Exception as e:
                return {"marketplace": f"unavailable, plugins not updated: {get_exception_summary(e)}"}
            by_id = {entry["id"]: entry for entry in marketplace}
            by_name = {(entry["author"], entry["name"]): entry for entry in marketplace}
            for plugin in installed:
                key = (plugin["author"], plugin["name"])
                license_info = licenses.get(key)
                entry = (by_id.get(license_info["plugin_id"]) if license_info else None) or by_name.get(key)
                if not entry:
                    continue
                name = f"{plugin['author']}/{plugin['name']}"
                if not entry["plugin_version"]:
                    results[name] = f"no version compatible with Bitcart {VERSION}, keeping {plugin['version']}"
                    continue
                try:
                    is_newer = Version(entry["plugin_version"]) > Version(plugin["version"])
                except InvalidVersion:
                    continue
                if not is_newer:
                    continue
                try:
                    result = await self.install_marketplace_version(session, entry, license_info)
                except Exception as e:
                    result = {"status": "error", "message": get_exception_summary(e)}
                if result["status"] == "success":
                    results[name] = f"updated to {entry['plugin_version']}"
                else:
                    results[name] = f"update to {entry['plugin_version']} failed: {result['message']}"
        return results

    async def install_marketplace_version(
        self, session: ClientSession, entry: dict[str, Any], license_info: dict[str, Any] | None
    ) -> dict[str, Any]:
        params = {"bitcart_version": VERSION, "version": entry["plugin_version"]}
        if license_info:
            params["license_key"] = license_info["license_key"]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "plugin.bitcart")
            async with session.get(
                f"{self.settings.LICENSE_SERVER_URL}/plugins/{entry['id']}/download", params=params
            ) as resp:
                if resp.status != 200:
                    return {"status": "error", "message": f"download returned HTTP {resp.status}: {await resp.text()}"}
                async with aiofiles.open(path, "wb") as f:
                    await f.write(await resp.read())
            return await self.install_from_archive(path)

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
