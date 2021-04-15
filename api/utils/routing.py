from collections import defaultdict
from dataclasses import dataclass
from os.path import join as path_join
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type, Union

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import SecurityScopes
from pydantic import BaseModel
from pydantic import create_model as create_pydantic_model
from sqlalchemy import distinct
from starlette.requests import Request

from api import db, events, models, pagination
from api.utils.authorization import AuthDependency
from api.utils.database import safe_db_write

HTTP_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
ENDPOINTS: List[str] = ["get_all", "get_one", "get_count", "post", "put", "patch", "delete", "batch_action"]
CUSTOM_HTTP_METHODS: dict = {"batch_action": "post"}


@dataclass
class ModelView:
    from api import schemes

    crud_models: ClassVar[list] = []

    router: APIRouter
    path: str
    orm_model: db.db.Model
    create_model: Any
    pydantic_model: Any
    display_model: Any
    allowed_methods: List[str]
    custom_methods: Dict[str, Callable]
    background_tasks_mapping: Dict[str, Callable]
    request_handlers: Dict[str, Callable]
    auth_dependency: AuthDependency
    get_one_auth: bool
    post_auth: bool
    get_one_model: bool
    scopes: Union[List, Dict]
    custom_commands: Dict[str, Callable]
    using_router: bool

    @classmethod
    def register(
        cls,
        router: APIRouter,
        path: str,
        orm_model,
        pydantic_model,
        create_model=None,
        display_model=None,
        allowed_methods: List[str] = ["GET_COUNT", "GET_ONE"] + HTTP_METHODS + ["BATCH_ACTION"],
        custom_methods: Dict[str, Callable] = {},
        background_tasks_mapping: Dict[str, Callable] = {},
        request_handlers: Dict[str, Callable] = {},
        auth=True,
        get_one_auth=True,
        post_auth=True,
        get_one_model=True,
        scopes=None,
        custom_commands={},
        using_router=True,
    ):
        # add to crud_models
        if scopes is None:  # pragma: no cover
            scopes = {i: [] for i in ENDPOINTS}
        cls.crud_models.append(orm_model)
        # set scopes
        if isinstance(scopes, list):
            scopes_list = scopes.copy()
            scopes = {i: scopes_list for i in ENDPOINTS}
        scopes = defaultdict(list, **scopes)

        if not create_model:
            create_model = pydantic_model  # pragma: no cover
        cls(
            router=router,
            path=path,
            orm_model=orm_model,
            pydantic_model=pydantic_model,
            create_model=create_model,
            display_model=display_model,
            allowed_methods=allowed_methods,
            custom_methods=custom_methods,
            background_tasks_mapping=background_tasks_mapping,
            request_handlers=request_handlers,
            auth_dependency=AuthDependency(auth),
            get_one_auth=get_one_auth,
            post_auth=post_auth,
            get_one_model=get_one_model,
            scopes=scopes,
            custom_commands=custom_commands,
            using_router=using_router,
        ).register_routes()

    def register_routes(self):
        response_models = self.get_response_models()
        paths = self.get_paths()
        for method in self.allowed_methods:
            method_name = method.lower()
            self.router.add_api_route(
                paths.get(method_name),  # type: ignore
                self.request_handlers.get(method_name)
                or getattr(self, method_name, None)
                or getattr(self, f"_{method_name}")(),
                methods=[method_name if method in HTTP_METHODS else CUSTOM_HTTP_METHODS.get(method_name, "get")],
                response_model=response_models.get(method_name),
            )

    def get_paths(self) -> Dict[str, str]:
        item_path = path_join(self.path, "{model_id}")
        batch_path = path_join(self.path, "batch")
        count_path = path_join(self.path, "count")
        base_path = self.path
        if self.using_router:
            base_path = base_path.lstrip("/")
        return {
            "get": base_path,
            "get_count": count_path,
            "get_one": item_path,
            "post": base_path,
            "put": item_path,
            "patch": item_path,
            "delete": item_path,
            "batch_action": batch_path,
        }

    def get_response_models(self) -> Dict[str, Type]:
        display_model = self.pydantic_model if not self.display_model else self.display_model
        pagination_response = get_pagination_model(display_model)
        return {
            "get": pagination_response,
            "get_count": int,
            "get_one": display_model if self.get_one_model else None,
            "post": display_model,
            "put": display_model,
            "patch": display_model,
            "delete": display_model,
        }

    async def _get_one(self, model_id: int, user: schemes.User, internal: bool = False):
        query = self.orm_model.query
        if self.orm_model != models.User and user:
            query = query.where(self.orm_model.user_id == user.id)
        item = await query.where(self.orm_model.id == model_id).gino.first()
        if self.custom_methods.get("get_one"):
            item = await self.custom_methods["get_one"](model_id, user, item, internal)
        if not item:
            raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
        return item

    def _get(self):
        async def get(
            pagination: pagination.Pagination = Depends(),
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["get_all"]),
        ):
            if self.custom_methods.get("get"):
                return await self.custom_methods["get"](pagination, user)
            else:
                return await pagination.paginate(self.orm_model, user.id)

        return get

    def _get_count(self):
        async def get_count(
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["get_count"])
        ):
            return (
                await (
                    (
                        self.orm_model.query.where(self.orm_model.user_id == user.id)
                        if self.orm_model != models.User
                        else self.orm_model.query
                    )
                    .with_only_columns([db.db.func.count(distinct(self.orm_model.id))])
                    .order_by(None)
                    .gino.scalar()
                )
                or 0
            )

        return get_count

    async def get_one(self, model_id: int, request: Request):
        try:
            user = await self.auth_dependency(request, SecurityScopes(self.scopes["get_one"]))
        except HTTPException:
            if self.get_one_auth:
                raise
            user = None
        return await self._get_one(model_id, user)

    def _post(self):
        async def post(model: self.create_model, request: Request):
            try:
                user = await self.auth_dependency(request, SecurityScopes(self.scopes["post"]))
            except HTTPException:
                if self.post_auth:
                    raise
                user = None
            with safe_db_write():
                if self.custom_methods.get("post"):
                    obj = await self.custom_methods["post"](model, user)
                else:
                    obj = await self.orm_model.create(**model.dict())  # type: ignore # pragma: no cover
            if self.background_tasks_mapping.get("post"):
                await events.event_handler.publish(self.background_tasks_mapping["post"], {"id": obj.id})
            return obj

        return post

    def _put(self):
        async def put(
            model_id: int,
            model: self.pydantic_model,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["put"]),
        ):  # type: ignore
            item = await self._get_one(model_id, user, True)
            with safe_db_write():
                if self.custom_methods.get("put"):
                    await self.custom_methods["put"](item, model, user)  # pragma: no cover
                else:
                    await item.update(**model.dict()).apply()  # type: ignore
            return item

        return put

    def _patch(self):
        async def patch(
            model_id: int,
            model: self.pydantic_model,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["patch"]),
        ):  # type: ignore
            item = await self._get_one(model_id, user, True)
            with safe_db_write():
                if self.custom_methods.get("patch"):
                    await self.custom_methods["patch"](item, model, user)  # pragma: no cover
                else:
                    await item.update(**model.dict(exclude_unset=True)).apply()  # type: ignore
            return item

        return patch

    def _delete(self):
        async def delete(
            model_id: int,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["delete"]),
        ):
            item = await self._get_one(model_id, user, True)
            if self.custom_methods.get("delete"):
                await self.custom_methods["delete"](item, user)
            else:
                await item.delete()
            return item

        return delete

    def process_command(self, command):
        if command in self.custom_commands:
            return self.custom_commands[command](self.orm_model)
        if command == "delete":
            return self.orm_model.delete

    def _batch_action(self):
        async def batch_action(
            settings: ModelView.schemes.BatchSettings,
            user: Union[None, ModelView.schemes.User] = Security(self.auth_dependency, scopes=self.scopes["batch_action"]),
        ):
            query = self.process_command(settings.command)
            if query is None:
                raise HTTPException(status_code=404, detail="Batch command not found")
            if self.orm_model != models.User and user:
                query = query.where(self.orm_model.user_id == user.id)
            query = query.where(self.orm_model.id.in_(settings.ids))
            if self.custom_methods.get("batch_action"):
                await self.custom_methods["batch_action"](query, settings, user)  # pragma: no cover
            else:  # pragma: no cover
                await query.gino.status()
            return True

        return batch_action


def get_pagination_model(display_model):
    return create_pydantic_model(
        f"PaginationResponse_{display_model.__name__}",
        count=(int, ...),
        next=(Optional[str], None),
        previous=(Optional[str], None),
        result=(List[display_model], ...),
        __base__=BaseModel,
    )
