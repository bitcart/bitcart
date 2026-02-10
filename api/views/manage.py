from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, File, Security, UploadFile

from api import constants, models, utils
from api.constants import AuthScopes
from api.schemas.policies import BackupsPolicy, GlobalStorePolicy, Policy
from api.services.backup_manager import BackupManager
from api.services.coins import CoinService
from api.services.management import ManagementService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService

router = APIRouter(route_class=DishkaRoute)


@router.get("/policies")
async def get_policies(
    setting_service: FromDishka[SettingService],
    plugin_registry: FromDishka[PluginRegistry],
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    data = await setting_service.get_setting(Policy)
    exclude = set()
    if not user:
        exclude = data._SECRET_FIELDS
    return await plugin_registry.apply_filters("get_global_policies", data.model_dump(exclude=exclude))


@router.post("/policies", response_model=Policy)
async def set_policies(
    setting_service: FromDishka[SettingService],
    settings: Policy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await setting_service.set_setting(settings)


@router.get("/stores", response_model=GlobalStorePolicy)
async def get_store_policies(setting_service: FromDishka[SettingService]) -> Any:
    return await setting_service.get_setting(GlobalStorePolicy)


@router.post("/stores", response_model=GlobalStorePolicy)
async def set_store_policies(
    setting_service: FromDishka[SettingService],
    settings: GlobalStorePolicy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await setting_service.set_setting(settings)


@router.post("/restart")
async def restart_server(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.restart_server()


@router.post("/plugin-reload")
async def plugin_reload(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.plugin_reload()


@router.post("/update")
async def update_server(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.update_server()


@router.post("/cleanup/images")
async def cleanup_images(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.cleanup_images()


@router.post("/cleanup/logs")
async def cleanup_logs(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.cleanup_logs()


@router.post("/cleanup")
async def cleanup_server(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.cleanup_server()


@router.get("/logs")
async def get_logs_list(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.get_logs_list()


@router.get("/logs/{log}")
async def get_log_contents(
    management_service: FromDishka[ManagementService],
    log: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.get_log_contents(log)


@router.delete("/logs/{log}")
async def delete_log(
    management_service: FromDishka[ManagementService],
    log: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.delete_log(log)


@router.get("/syncinfo")
async def get_syncinfo(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.get_syncinfo()


@router.get("/testping")
async def test_email_ping(
    management_service: FromDishka[ManagementService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await management_service.test_server_email()


@router.get("/daemons")
async def get_daemons(
    coin_service: FromDishka[CoinService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return coin_service.crypto_settings


@router.get("/backups", response_model=BackupsPolicy)
async def get_backup_policies(
    setting_service: FromDishka[SettingService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await setting_service.get_setting(BackupsPolicy)


@router.post("/backups", response_model=BackupsPolicy)
async def set_backup_policies(
    backups_manager: FromDishka[BackupManager],
    settings: BackupsPolicy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await backups_manager.set_backup_policies(settings)


@router.get("/backups/providers")
async def get_backup_providers() -> Any:
    return constants.BACKUP_PROVIDERS


@router.get("/backups/frequencies")
async def get_backup_frequencies() -> Any:
    return constants.BACKUP_FREQUENCIES


@router.post("/backups/backup")
async def perform_backup(
    backups_manager: FromDishka[BackupManager],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await backups_manager.perform_backup_for_client()


@router.get("/backups/download/{file_id}")
async def download_backup(
    backup_manager: FromDishka[BackupManager],
    file_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await backup_manager.download_backup(file_id)


@router.post("/backups/restore")
async def restore_backup(
    backup_manager: FromDishka[BackupManager],
    backup: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await backup_manager.restore_backup(backup)
