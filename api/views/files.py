import os
from typing import Any

from dishka import FromDishka
from fastapi import File, Security, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.staticfiles import NotModifiedResponse, PathLike, StaticFiles
from starlette.types import Scope

from api import models, utils
from api.constants import AuthScopes
from api.schemas.files import CreateFile, DisplayFile, UpdateFile
from api.services.crud.files import FileService, get_original_name
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


class UserFilesStaticFiles(StaticFiles):
    def file_response(
        self, full_path: PathLike, stat_result: os.stat_result, scope: Scope, status_code: int = 200
    ) -> Response:
        original_name = get_original_name(os.path.basename(full_path))
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result, filename=original_name)
        if self.is_not_modified(response.headers, Headers(scope=scope)):
            return NotModifiedResponse(response.headers)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "sandbox"
        return response
