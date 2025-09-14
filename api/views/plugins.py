from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, File, HTTPException, Security, UploadFile

from api import models, utils
from api.constants import AuthScopes
from api.schemas.plugins import AddLicenseRequest, UninstallPluginData
from api.services.plugin_manager import PluginManager
from api.services.plugin_registry import PluginRegistry

router = APIRouter(route_class=DishkaRoute)


@router.get("")
async def get_plugins(
    plugin_manager: FromDishka[PluginManager],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> dict[str, Any]:
    return plugin_manager.get_installed_plugins()


@router.post("/install")
async def install_plugin(
    plugin_manager: FromDishka[PluginManager],
    plugin: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await plugin_manager.install_plugin(plugin)


@router.post("/uninstall")
async def uninstall_plugin(
    plugin_manager: FromDishka[PluginManager],
    data: UninstallPluginData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    try:
        plugin_manager.uninstall_plugin(data.author, data.name)
    except ValueError:
        return False
    return True


@router.get("/settings/list")
async def get_plugins_list(
    plugin_registry: FromDishka[PluginRegistry],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return plugin_registry.get_registered_plugins()


@router.get("/settings/{plugin_name}")
async def get_plugin_settings(
    plugin_registry: FromDishka[PluginRegistry],
    plugin_name: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    settings = await plugin_registry.get_plugin_settings(plugin_name)
    if not settings:
        raise HTTPException(404, "Plugin settings not found")
    return settings


@router.post("/settings/{plugin_name}")
async def update_plugin_settings(
    plugin_registry: FromDishka[PluginRegistry],
    plugin_name: str,
    settings: dict[str, Any],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    success, settings_obj = await plugin_registry.set_plugin_settings_dict(plugin_name, settings)
    if not success:
        raise HTTPException(404, "Plugin settings not found")
    return settings_obj


@router.post("/licenses")
async def add_license(
    plugin_manager: FromDishka[PluginManager],
    request: AddLicenseRequest,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await plugin_manager.add_license(request.license_key)


@router.get("/licenses")
async def get_licenses(
    plugin_manager: FromDishka[PluginManager],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await plugin_manager.get_licenses()


@router.delete("/licenses/{license_key}")
async def delete_license(
    plugin_manager: FromDishka[PluginManager],
    license_key: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await plugin_manager.delete_license(license_key)
