import os
import tempfile

import aiofiles
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, File, HTTPException, Security, UploadFile

from api import constants, models, schemes, settings, utils
from api.ext import backups as backups_ext

router = APIRouter()

# Docker deployment maintenance commands


@router.post("/restart")
async def restart_server(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        return utils.host.run_host_output("./restart.sh", "Successfully started restart process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/update")
async def update_server(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        return utils.host.run_host_output("./update.sh", "Successfully started update process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/cleanup/images")
async def cleanup_images(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        return utils.host.run_host_output("./cleanup.sh", "Successfully started cleanup process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/cleanup/logs")
async def cleanup_logs(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if not settings.settings.log_file:
        return {"status": "error", "message": "Log file unconfigured"}
    for f in os.listdir(settings.settings.log_dir):
        if utils.logging.log_filter(f):
            try:
                os.remove(os.path.join(settings.settings.log_dir, f))
            except OSError:  # pragma: no cover
                pass
    return {"status": "success", "message": "Successfully cleaned up logs!"}


@router.post("/cleanup")
async def cleanup_server(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    data = [await cleanup_images(), await cleanup_logs()]
    message = ""
    for result in data:
        if result["status"] != "success":
            message += f"{result['message']}\n"
        else:
            return {"status": "success", "message": "Successfully started cleanup process!"}
    return {"status": "error", "message": message}


@router.get("/daemons")
async def get_daemons(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    return settings.settings.crypto_settings


@router.get("/policies", response_model=schemes.Policy)
async def get_policies():
    return await utils.policies.get_setting(schemes.Policy)


@router.post("/policies", response_model=schemes.Policy)
async def set_policies(
    settings: schemes.Policy,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    return await utils.policies.set_setting(settings)


@router.get("/stores", response_model=schemes.GlobalStorePolicy)
async def get_store_policies():
    return await utils.policies.get_setting(schemes.GlobalStorePolicy)


@router.post("/stores", response_model=schemes.GlobalStorePolicy)
async def set_store_policies(
    settings: schemes.GlobalStorePolicy,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    return await utils.policies.set_setting(settings)


@router.get("/logs")
async def get_logs_list(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if not settings.settings.log_file:
        return []
    data = sorted((f for f in os.listdir(settings.settings.log_dir) if utils.logging.log_filter(f)), reverse=True)
    if os.path.exists(settings.settings.log_file):
        data = [settings.settings.log_file_name] + data
    return data


@router.get("/logs/{log}")
async def get_log_contents(
    log: str, user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])
):
    if not settings.settings.log_file:
        raise HTTPException(400, "Log file unconfigured")
    try:
        with open(os.path.join(settings.settings.log_dir, log)) as f:
            contents = f.read().strip()
        return contents
    except OSError:
        raise HTTPException(404, "This log doesn't exist")


@router.delete("/logs/{log}")
async def delete_log(
    log: str, user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])
):
    if not settings.settings.log_file:
        raise HTTPException(400, "Log file unconfigured")
    if log == settings.settings.log_file_name:
        raise HTTPException(403, "Forbidden to delete current log file")
    try:
        os.remove(os.path.join(settings.settings.log_dir, log))
        return True
    except OSError:
        raise HTTPException(404, "This log doesn't exist")


@router.get("/backups", response_model=schemes.BackupsPolicy)
async def get_backup_policies(
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])
):
    return await utils.policies.get_setting(schemes.BackupsPolicy)


@router.post("/backups", response_model=schemes.BackupsPolicy)
async def set_backup_policies(
    settings: schemes.BackupsPolicy,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    async with backups_ext.manager.lock:
        old_settings = await utils.policies.get_setting(schemes.BackupsPolicy)
        got = await utils.policies.set_setting(settings)
        await backups_ext.manager.process_new_policy(old_settings, got)
        return got


@router.get("/backups/providers")
async def get_backup_providers():
    return constants.BACKUP_PROVIDERS


@router.get("/backups/frequencies")
async def get_backup_frequencies():
    return constants.BACKUP_FREQUENCIES


@router.post("/backups/backup")
async def perform_backup(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        return await backups_ext.manager.perform_backup()
    return {"status": "error", "message": "Not running in docker"}


@router.post("/backups/restore")
async def restore_backup(
    backup: UploadFile = File(...),
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"]),
):
    if settings.settings.docker_env:  # pragma: no cover
        path = os.path.join(tempfile.mkdtemp(), "backup.tar.gz")
        async with aiofiles.open(path, "wb") as f:
            await f.write(await backup.read())
        return utils.host.run_host_output(f"./restore.sh --delete-backup {path}", "Successfully started restore process!")
    return {"status": "error", "message": "Not running in docker"}


@router.get("/syncinfo")
async def get_syncinfo(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["server_management"])):
    infos = []
    for coin in settings.settings.cryptos:
        info = {"running": True, "currency": settings.settings.cryptos[coin].coin_name}
        try:
            info.update(await settings.settings.cryptos[coin].server.getinfo())
        except BitcartBaseError:
            info["running"] = False
        infos.append(info)
    return infos
