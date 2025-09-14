from typing import Any

from dishka import FromDishka
from fastapi import File, Security, UploadFile
from fastapi.responses import RedirectResponse

from api import models, utils
from api.constants import AuthScopes
from api.schemas.files import CreateFile, DisplayFile, UpdateFile
from api.services.crud.files import FileService
from api.utils.routing import create_crud_router

router = create_crud_router(
    CreateFile,
    UpdateFile,
    DisplayFile,
    FileService,
    required_scopes=[AuthScopes.FILE_MANAGEMENT],
    disabled_endpoints={"create": True, "update": True},
)


@router.post("", response_model=DisplayFile)
async def create_file(
    file_service: FromDishka[FileService],
    file: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.FILE_MANAGEMENT]),
) -> Any:
    return await file_service.create_file(file, user)


@router.patch("/{model_id}", response_model=DisplayFile)
async def patch_file(
    file_service: FromDishka[FileService],
    model_id: str,
    file: UploadFile = File(...),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.FILE_MANAGEMENT]),
) -> Any:
    return await file_service.update_file(model_id, file, user)


@router.get("/handle/{model_id}")
async def handle_file(file_service: FromDishka[FileService], model_id: str) -> Any:
    return RedirectResponse(await file_service.handle_file(model_id))
