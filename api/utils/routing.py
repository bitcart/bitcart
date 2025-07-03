from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from os.path import join as path_join
from typing import Any, ClassVar
from urllib import parse as urlparse

from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel
from pydantic import create_model as create_pydantic_model
from starlette.requests import Request

from api import db, events, models, pagination, settings, utils

HTTP_METHODS: list[str] = ["GET", "POST", "PATCH", "DELETE"]
ENDPOINTS: list[str] = ["get_all", "get_one", "get_count", "post", "patch", "delete", "batch_action"]
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
    allowed_methods: list[str]
    custom_methods: dict[str, Callable]
    background_tasks_mapping: dict[str, Callable]
    request_handlers: dict[str, Callable]
    get_one_auth: bool
    post_auth: bool
    get_one_model: bool
    scopes: list | dict
    custom_commands: dict[str, Callable]
    using_router: bool
    response_models: dict[str, BaseModel]

    @classmethod
    def register(
        cls,
        router: APIRouter,
        path: str,
        orm_model,
        pydantic_model,
        create_model=None,
        display_model=None,
        allowed_methods: list[str] = ["GET_COUNT", "GET_ONE"] + HTTP_METHODS + ["BATCH_ACTION"],
        custom_methods: dict[str, Callable] = None,
        background_tasks_mapping: dict[str, Callable] = None,
        request_handlers: dict[str, Callable] = None,
        get_one_auth=True,
        post_auth=True,
        get_one_model=True,
        scopes=None,
        custom_commands=None,
        using_router=True,
        response_models: dict[str, BaseModel] = None,
    ):
        # add to crud_models
        if response_models is None:
            response_models = {}
        if custom_commands is None:
            custom_commands = {}
        if request_handlers is None:
            request_handlers = {}
        if background_tasks_mapping is None:
            background_tasks_mapping = {}
        if custom_methods is None:
            custom_methods = {}
        if scopes is None:  # pragma: no cover
            scopes = {i: [] for i in ENDPOINTS}
        cls.crud_models.append(orm_model)
        # set scopes
        if isinstance(scopes, list):
            scopes_list = scopes.copy()
            scopes = dict.fromkeys(ENDPOINTS, scopes_list)
        scopes = defaultdict(list, **scopes)

        if not create_model:
            create_model = pydantic_model  # pragma: no cover
        return cls(
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
            get_one_auth=get_one_auth,
            post_auth=post_auth,
            get_one_model=get_one_model,
            scopes=scopes,
            custom_commands=custom_commands,
            using_router=using_router,
            response_models=response_models,
        ).register_routes()

    def register_routes(self):
        response_models = self.get_response_models()
        paths = self.get_paths()
        names = self.get_names()
        for method in self.allowed_methods:
            method_name = method.lower()
            self.router.add_api_route(
                paths.get(method_name),
                self.request_handlers.get(method_name)
                or getattr(self, method_name, None)
                or getattr(self, f"_{method_name}")(),
                name=names.get(method_name),
                methods=[method_name if method in HTTP_METHODS else CUSTOM_HTTP_METHODS.get(method_name, "get")],
                response_model=self.response_models.get(method_name, response_models.get(method_name)),
            )
        return self

    def get_paths(self) -> dict[str, str]:
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
            "patch": item_path,
            "delete": item_path,
            "batch_action": batch_path,
        }

    def get_names(self) -> dict[str, str]:
        return {
            "get": f"Get {self.orm_model.__name__}s",
            "get_count": f"Get number of {self.orm_model.__name__}s",
            "get_one": f"Get {self.orm_model.__name__} by id",
            "post": f"Create {self.orm_model.__name__}",
            "patch": f"Modify {self.orm_model.__name__}",
            "delete": f"Delete {self.orm_model.__name__}",
            "batch_action": f"Batch actions on {self.orm_model.__name__}s",
        }

    def get_response_models(self) -> dict[str, type]:
        display_model = self.pydantic_model if not self.display_model else self.display_model
        pagination_response = get_pagination_model(display_model)
        return {
            "get": pagination_response,
            "get_count": int,
            "get_one": display_model if self.get_one_model else None,
            "post": display_model,
            "patch": display_model,
            "delete": display_model,
        }

    async def _get_one_internal(self, model_id: str, user: schemes.User, internal: bool = False):
        item = await utils.database.get_object(self.orm_model, model_id, user if self.get_one_auth else None)
        if self.custom_methods.get("get_one"):
            item = await self.custom_methods["get_one"](model_id, user, item, internal)
        return item

    def _get(self):
        async def get(
            request: Request,
            pagination: pagination.Pagination = Depends(),
            user: models.User = Security(utils.authorization.auth_dependency, scopes=self.scopes["get_all"]),
        ):
            params = utils.common.prepare_query_params(request)
            if self.custom_methods.get("get"):
                return await self.custom_methods["get"](pagination, user, **params)  # pragma: no cover
            return await utils.database.paginate_object(self.orm_model, pagination, user, **params)

        return get

    def _get_count(self):
        async def get_count(
            user: models.User = Security(utils.authorization.auth_dependency, scopes=self.scopes["get_count"]),
        ):
            return await utils.database.get_scalar(
                (
                    self.orm_model.query.where(self.orm_model.user_id == user.id)
                    if self.orm_model != models.User
                    else self.orm_model.query
                ),
                db.db.func.count,
                self.orm_model.id,
            )

        return get_count

    def _get_one(self):
        async def get_one(
            model_id: str,
            user: models.User | None = Security(
                (utils.authorization.auth_dependency if self.get_one_auth else utils.authorization.optional_auth_dependency),
                scopes=self.scopes["get_one"],
            ),
        ):
            return await self._get_one_internal(model_id, user)

        return get_one

    def _post(self):
        async def post(
            model: self.create_model,
            user: models.User | None = Security(
                (utils.authorization.auth_dependency if self.post_auth else utils.authorization.optional_auth_dependency),
                scopes=self.scopes["post"],
            ),
        ):
            if self.custom_methods.get("post"):
                obj = await self.custom_methods["post"](model, user)
            else:
                obj = await utils.database.create_object(self.orm_model, model, user)
            if self.background_tasks_mapping.get("post"):
                await events.event_handler.publish(self.background_tasks_mapping["post"], {"id": obj.id})
            return obj

        return post

    def _patch(self):
        async def patch(
            model_id: str,
            model: utils.schemes.to_optional(self.pydantic_model),
            user: models.User = Security(utils.authorization.auth_dependency, scopes=self.scopes["patch"]),
        ):
            item = await self._get_one_internal(model_id, user, True)
            if self.custom_methods.get("patch"):
                await self.custom_methods["patch"](item, model, user)  # pragma: no cover
            else:
                await utils.database.modify_object(item, model.model_dump(exclude_unset=True))
            return item

        return patch

    def _delete(self):
        async def delete(
            model_id: str,
            user: models.User = Security(utils.authorization.auth_dependency, scopes=self.scopes["delete"]),
        ):
            item = await self._get_one_internal(model_id, user, True)
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
            user: models.User = Security(utils.authorization.auth_dependency, scopes=self.scopes["batch_action"]),
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
        next=(str | None, None),
        previous=(str | None, None),
        result=(list[display_model], ...),
        __base__=BaseModel,
    )


def get_redirect_url(url, **kwargs):
    parsed = urlparse.urlparse(url)
    query = parsed.query
    url_dict = dict(urlparse.parse_qs(query))
    for key in kwargs:
        if key not in url_dict:
            url_dict[key] = kwargs[key]
        else:
            url_dict[key].append(kwargs[key])
    url_new_query = urlparse.urlencode(url_dict, doseq=True)
    parsed = parsed._replace(query=url_new_query)
    return urlparse.urlunparse(parsed)


def prepare_next_url(path):
    return urlparse.urljoin(settings.settings.admin_url, path)
