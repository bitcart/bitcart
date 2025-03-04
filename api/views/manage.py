import asyncio
import contextlib
import os

import aiofiles
from bitcart.errors import BaseError as BitcartBaseError
from fastapi import APIRouter, File, HTTPException, Security, UploadFile
from fastapi.responses import FileResponse

from api import constants, models, schemes, settings, utils
from api.ext import backups as backups_ext
from api.plugins import run_hook

router = APIRouter()

# Docker deployment maintenance commands


@router.post("/restart")
async def restart_server(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        await run_hook("server_restart")
        return utils.host.run_host_output("./restart.sh", "Successfully started restart process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/plugin-reload")
async def plugin_reload(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        await run_hook("plugin_reload")
        return utils.host.run_host_output("./start.sh", "Successfully started plugin reload process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/update")
async def update_server(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        await run_hook("server_update")
        policy = await utils.policies.get_setting(schemes.Policy)
        run_script = "./install-master.sh" if policy.staging_updates else "./update.sh"
        return utils.host.run_host_output(run_script, "Successfully started update process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/cleanup/images")
async def cleanup_images(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        await run_hook("server_cleanup_images")
        return utils.host.run_host_output("./cleanup.sh", "Successfully started cleanup process!")
    return {"status": "error", "message": "Not running in docker"}


@router.post("/cleanup/logs")
async def cleanup_logs(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if not settings.settings.log_file:
        return {"status": "error", "message": "Log file unconfigured"}
    for f in os.listdir(settings.settings.log_dir):
        if utils.logging.log_filter(f):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(settings.settings.log_dir, f))
    return {"status": "success", "message": "Successfully cleaned up logs!"}


@router.post("/cleanup")
async def cleanup_server(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    data = [await cleanup_images(), await cleanup_logs()]
    message = ""
    for result in data:
        if result["status"] != "success":
            message += f"{result['message']}\n"
        else:
            return {"status": "success", "message": "Successfully started cleanup process!"}
    return {"status": "error", "message": message}


@router.get("/daemons")
async def get_daemons(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    return settings.settings.crypto_settings


@router.get("/policies")
async def get_policies(
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=["server_management"]),
):
    data = await utils.policies.get_setting(schemes.Policy)
    exclude = set()
    if not user:
        exclude = data._SECRET_FIELDS
    return data.model_dump(exclude=exclude)


@router.post("/policies", response_model=schemes.Policy)
async def set_policies(
    settings: schemes.Policy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    return await utils.policies.set_setting(settings)


@router.get("/stores", response_model=schemes.GlobalStorePolicy)
async def get_store_policies():
    return await utils.policies.get_setting(schemes.GlobalStorePolicy)


@router.post("/stores", response_model=schemes.GlobalStorePolicy)
async def set_store_policies(
    settings: schemes.GlobalStorePolicy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    return await utils.policies.set_setting(settings)


@router.get("/logs")
async def get_logs_list(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if not settings.settings.log_file:
        return []
    data = sorted((f for f in os.listdir(settings.settings.log_dir) if utils.logging.log_filter(f)), reverse=True)
    if os.path.exists(settings.settings.log_file):
        data = [settings.settings.log_file_name] + data
    return data


@router.get("/logs/{log}")
async def get_log_contents(
    log: str, user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])
):
    if not settings.settings.log_file:
        raise HTTPException(400, "Log file unconfigured")
    try:
        async with aiofiles.open(os.path.join(settings.settings.log_dir, log)) as f:
            return (await f.read()).strip()
    except OSError:
        raise HTTPException(404, "This log doesn't exist") from None


@router.delete("/logs/{log}")
async def delete_log(
    log: str, user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])
):
    if not settings.settings.log_file:
        raise HTTPException(400, "Log file unconfigured")
    if log == settings.settings.log_file_name:
        raise HTTPException(403, "Forbidden to delete current log file")
    try:
        os.remove(os.path.join(settings.settings.log_dir, log))
        return True
    except OSError:
        raise HTTPException(404, "This log doesn't exist") from None


@router.get("/backups", response_model=schemes.BackupsPolicy)
async def get_backup_policies(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    return await utils.policies.get_setting(schemes.BackupsPolicy)


@router.post("/backups", response_model=schemes.BackupsPolicy)
async def set_backup_policies(
    settings: schemes.BackupsPolicy,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
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
async def perform_backup(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    if settings.settings.docker_env:  # pragma: no cover
        output = await backups_ext.manager.perform_backup()
        message = output["message"]
        if output["status"] == "success":
            output["message"] = "Successfully performed backup!"
            lines = message.splitlines()
            for line in lines:
                if line.startswith("Backed up to"):
                    filename = os.path.basename(line.split()[-1])
                    file_id = utils.common.unique_id()
                    async with utils.redis.wait_for_redis():
                        await settings.settings.redis_pool.set(f"backups:{file_id}", filename)
                    return {"status": "success", "message": output["message"], "file_id": file_id}
        return output
    return {"status": "error", "message": "Not running in docker"}


@router.get("/backups/download/{file_id}")
async def download_backup(
    file_id: str, user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])
):
    if settings.settings.docker_env:  # pragma: no cover
        async with utils.redis.wait_for_redis():
            filename = await settings.settings.redis_pool.execute_command("GETDEL", f"backups:{file_id}")
        if filename:
            headers = {"Content-Disposition": f"attachment; filename={os.path.basename(filename)}"}
            return FileResponse(os.path.join(settings.settings.backups_dir, filename), headers=headers)
        raise HTTPException(404, "This backup doesn't exist")
    raise HTTPException(400, "Not running in docker")


@router.post("/backups/restore")
async def restore_backup(
    backup: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"]),
):
    if settings.settings.docker_env:  # pragma: no cover
        path = os.path.join(settings.settings.datadir, "backup.tar.gz")
        async with aiofiles.open(path, "wb") as f:
            await f.write(await backup.read())
        await run_hook("restore_backup", path)
        return utils.host.run_host_output(
            '. helpers.sh; load_env; ./restore.sh --delete-backup "/var/lib/docker/volumes/$(volume_name'
            ' bitcart_datadir)/_data/backup.tar.gz" ',
            "Successfully started restore process!",
        )
    return {"status": "error", "message": "Not running in docker"}


async def fetch_currency_info(coin):
    info = {"running": True, "currency": settings.settings.cryptos[coin].coin_name}
    try:
        info.update(await settings.settings.cryptos[coin].server.getinfo())
    except BitcartBaseError:
        info["running"] = False
    return info


@router.get("/syncinfo")
async def get_syncinfo(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    coros = [fetch_currency_info(coin) for coin in settings.settings.cryptos]
    return await asyncio.gather(*coros)


@router.get("/testping")
async def test_email_ping(user: models.User = Security(utils.authorization.auth_dependency, scopes=["server_management"])):
    policy = await utils.policies.get_setting(schemes.Policy)
    return utils.Email.get_email(policy).check_ping()
