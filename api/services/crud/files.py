import os
from typing import Any

import aiofiles
from dishka import AsyncContainer
from fastapi import HTTPException, UploadFile

from api import models, utils
from api.db import AsyncSession
from api.schemas.policies import Policy
from api.services.crud import CRUDService
from api.services.crud.repositories import FileRepository
from api.services.settings import SettingService
from api.settings import Settings


class FileService(CRUDService[models.File]):
    repository_type = FileRepository

    def __init__(
        self, session: AsyncSession, container: AsyncContainer, settings: Settings, setting_service: SettingService
    ) -> None:
        super().__init__(session, container)
        self.settings = settings
        self.setting_service = setting_service

    def get_file_path(self, item: models.File) -> str:
        return os.path.join(self.settings.files_dir, f"{item.id}-{item.filename}")

    async def save_file(self, item: models.File, file: UploadFile) -> None:
        path = self.get_file_path(item)
        async with aiofiles.open(path, "wb") as f:
            await f.write(await file.read())

    def remove_file(self, item: models.File) -> None:
        utils.files.safe_remove(self.get_file_path(item))

    async def create_file(
        self,
        file: UploadFile,
        user: models.User,
    ) -> models.File:
        policy = await self.setting_service.get_setting(Policy)
        if not user.is_superuser and not policy.allow_file_uploads:
            raise HTTPException(403, "File uploads are not allowed")
        file_obj = await self.create({"filename": file.filename}, user)
        await self.save_file(file_obj, file)
        return file_obj

    async def update_file(self, model_id: str, file: UploadFile, user: models.User) -> models.File:
        policy = await self.setting_service.get_setting(Policy)
        if not user.is_superuser and not policy.allow_file_uploads:
            raise HTTPException(403, "File uploads are not allowed")
        item = await self.get(model_id, user)
        self.remove_file(item)
        item.update(filename=file.filename)
        await self.save_file(item, file)
        return item

    async def delete(self, item: models.File | str, user: models.User | None = None, **kwargs: Any) -> models.File:
        item = await super().delete(item, user, **kwargs)
        self.remove_file(item)
        return item

    async def delete_many(self, ids: list[str], user: models.User | None = None, **kwargs: Any) -> list[models.File]:
        items = await super().delete_many(ids, user, **kwargs)
        for item in items:
            self.remove_file(item)
        return items

    async def handle_file(self, model_id: str) -> str:
        item = await self.get(model_id)
        final_name = os.path.basename(self.get_file_path(item))
        return f"{self.settings.api_url}/files/localstorage/{final_name}"
