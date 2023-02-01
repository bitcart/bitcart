import os
import shutil
import tempfile

import aiofiles
from fastapi import APIRouter, File, Security, UploadFile

from api import models, schemes, settings, utils
from api.ext import plugins as plugin_ext

router = APIRouter()


@router.get("")
async def get_plugins(
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    failed_path = os.path.join(settings.settings.datadir, ".plugins-failed")
    is_error = os.path.exists(failed_path)
    return {"success": not is_error, "plugins": plugin_ext.get_plugins()}


@router.post("/install")
async def install_plugin(
    plugin: UploadFile = File(...),
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    filename = plugin.filename
    if not filename.endswith(".bitcartcc"):
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
    with open(manifest_path) as f:
        manifest = f.read()
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
async def uninstall_plugin(data: schemes.UninstallPluginData):
    try:
        plugin_ext.uninstall_plugin(data.author, data.name)
    except ValueError:
        return False
    return True
