import os

import aiofiles
from fastapi import APIRouter, File, HTTPException, Security, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from api import models, schemes, settings, utils

router = APIRouter()


def get_file_path(item):
    return os.path.join(settings.settings.files_dir, f"{item.id}-{item.filename}")


async def create_file(
    file: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["file_management"]),
):
    policy = await utils.policies.get_setting(schemes.Policy)
    if not user.is_superuser and not policy.allow_file_uploads:
        raise HTTPException(403, "File uploads are not allowed")
    file_obj = await utils.database.create_object(models.File, {"filename": file.filename}, user)
    path = get_file_path(file_obj)
    async with aiofiles.open(path, "wb") as f:
        await f.write(await file.read())
    return file_obj


async def patch_file(
    model_id: str,
    file: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["file_management"]),
):
    policy = await utils.policies.get_setting(schemes.Policy)
    if not user.is_superuser and not policy.allow_file_uploads:
        raise HTTPException(403, "File uploads are not allowed")
    item = await utils.database.get_object(models.File, model_id, user)
    utils.files.safe_remove(get_file_path(item))
    await utils.database.modify_object(item, {"filename": file.filename})
    path = get_file_path(item)
    async with aiofiles.open(path, "wb") as f:
        await f.write(await file.read())
    return item


async def delete_file(item: schemes.DisplayFile, user: schemes.User) -> schemes.DisplayFile:
    utils.files.safe_remove(get_file_path(item))
    await item.delete()
    return item


@router.get("/handle/{model_id}")
async def handle_file(model_id: str):
    item = await utils.database.get_object(models.File, model_id)
    final_name = os.path.basename(get_file_path(item))
    return RedirectResponse(f"/files/localstorage/{final_name}")


async def batch_file_action(query, batch_settings: schemes.BatchSettings, user: schemes.User):
    if batch_settings.command == "delete":
        for file_id, filename in (
            await select([models.File.id, models.File.filename]).where(models.File.id.in_(batch_settings.ids)).gino.all()
        ):
            utils.files.safe_remove(os.path.join(settings.settings.files_dir, f"{file_id}-{filename}"))
    await query.gino.status()
    return True


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.File,
    schemes.UpdateFile,
    schemes.CreateFile,
    schemes.DisplayFile,
    custom_methods={"delete": delete_file, "batch_action": batch_file_action},
    request_handlers={"post": create_file, "patch": patch_file},
    scopes=["file_management"],
)
