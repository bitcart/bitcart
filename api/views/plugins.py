import os
import shutil
import tempfile

import aiofiles
from fastapi import APIRouter, File, HTTPException, Security, UploadFile

from api import models, plugins, schemes, settings, utils
from api.ext import plugins as plugin_ext
from api.plugins import run_hook

router = APIRouter()


@router.get("")
async def get_plugins(
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    failed_path = os.path.join(settings.settings.datadir, ".plugins-failed")
    is_error = os.path.exists(failed_path)
    return {"success": not is_error, "plugins": plugin_ext.get_plugins()}


@router.post("/install")
async def install_plugin(
    plugin: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    filename = plugin.filename
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
        manifest = await f.read()
    try:
        manifest = plugin_ext.parse_manifest(manifest)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    final_path = os.path.join(
        settings.settings.plugins_dir, os.path.join(manifest["author"].lower(), manifest["name"].lower())
    )
    if os.path.exists(final_path):
        utils.files.remove_tree(final_path)
    shutil.move(plugin_path, final_path)
    plugin_ext.process_installation_hooks(final_path, manifest)
    return {
        "status": "success",
        "message": "Successfully installed plugin files. Restart your instance for plugin to load",
    }


@router.post("/uninstall")
async def uninstall_plugin(
    data: schemes.UninstallPluginData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    try:
        plugin_ext.uninstall_plugin(data.author, data.name)
    except ValueError:
        return False
    return True


@router.get("/settings/list")
async def get_plugins_list(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    return plugins.get_registered_plugins()


@router.get("/settings/{plugin_name}")
async def get_plugin_settings(
    plugin_name: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    settings = await plugins.get_plugin_settings(plugin_name)
    if not settings:
        raise HTTPException(404, "Plugin settings not found")
    return settings


@router.post("/settings/{plugin_name}")
async def update_plugin_settings(
    plugin_name: str,
    settings: dict,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    success, settings_obj = await plugins.set_plugin_settings_dict(plugin_name, settings)
    if not success:
        raise HTTPException(404, "Plugin settings not found")
    return settings_obj


@router.post("/licenses")
async def add_license(
    request: schemes.AddLicenseRequest,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    state = await utils.policies.get_setting(schemes.PluginsState)
    license_keys = state.license_keys
    if request.license_key in license_keys:
        raise HTTPException(status_code=400, detail="License key already added")
    try:
        license_info = await utils.common.send_request(
            "GET", f"{settings.settings.license_server_url}/licenses/{request.license_key}", return_json=False
        )
        if license_info[0].status != 200:
            raise HTTPException(status_code=400, detail="Invalid license key")
        license_info = await license_info[0].json()
        license_keys[request.license_key] = license_info
        state = schemes.PluginsState(**state.model_dump(exclude={"license_keys"}), license_keys=license_keys)
        await utils.policies.set_setting(state)
        await run_hook("license_changed", request.license_key, license_info)
        return license_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid license key: {str(e)}") from None


@router.get("/licenses")
async def get_licenses(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    state = await utils.policies.get_setting(schemes.PluginsState)
    return list(state.license_keys.values())


@router.delete("/licenses/{license_key}")
async def delete_license(
    license_key: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    state = await utils.policies.get_setting(schemes.PluginsState)
    license_info = state.license_keys.get(license_key)
    state.license_keys.pop(license_key, None)
    await utils.policies.set_setting(state)
    if license_info:
        await run_hook("license_changed", None, license_info)
    return True
