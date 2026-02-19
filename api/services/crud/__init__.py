from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, cast, overload

from advanced_alchemy.base import ModelProtocol
from advanced_alchemy.filters import StatementFilter, StatementTypeT
from advanced_alchemy.repository import LoadSpec
from advanced_alchemy.service.typing import ModelDictT
from dishka import AsyncContainer
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import ColumnElement, ColumnExpressionArgument, Select, Text, Update, and_, false, func, or_, select
from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.exc import NoResultFound, ProgrammingError

from api import models, utils
from api.db import AsyncSession
from api.schemas.base import Schema
from api.schemas.misc import BatchAction
from api.services.crud.repository import CRUDRepository
from api.utils.routing import SearchPagination


class CRUDAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


def unauthorized_access_exception() -> HTTPException:
    return HTTPException(403, "Access denied: attempt to use objects not owned by current user")


class CRUDService[ModelType: ModelProtocol]:
    session: AsyncSession
    repository_type: type[CRUDRepository[ModelType]]

    FKEY_MAPPING: dict[str, str] = {}

    @property
    def model_type(self) -> type[ModelType]:
        return self.repository_type.model_type

    def _check_data(self, data: "ModelDictT[ModelType]", update: bool = False) -> dict[str, Any]:
        if isinstance(data, Schema):
            data = data.model_dump(exclude_unset=update)
        if not isinstance(data, dict):
            raise ValueError("CRUDService doesn't support non-dict data")
        return data

    def __init__(self, session: AsyncSession, container: AsyncContainer) -> None:
        self.session = session
        self.container = container
        self.repository = self.repository_type(session=session)

    def _add_user_filter(self, filters: list[StatementFilter | ColumnElement[bool]], user: models.User | None) -> None:
        if user is not None and hasattr(self.model_type, "user_id"):
            user_id_attr = utils.common.get_sqla_attr(cast(ModelType, self.model_type), "user_id")
            filters.append(user_id_attr == utils.common.get_sqla_attr(user, "id"))

    async def _execute_get(
        self,
        method: Callable[..., Awaitable[ModelType | None]],
        item_id: Any,
        user: models.User | None = None,
        *args: Any,
        atomic_update: bool = False,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_load: bool = True,
        **kwargs: Any,
    ) -> ModelType | None:
        filter_list: list[StatementFilter | ColumnElement[bool]] = (
            [utils.common.get_sqla_attr(cast(ModelType, self.model_type), "id") == item_id] if item_id is not None else []
        )
        if filters:
            filter_list.extend(filters)
        self._add_user_filter(filter_list, user)
        if statement is None:
            statement = select(self.model_type)
        if atomic_update:
            statement = statement.with_for_update()
        result = await method(
            *filter_list,
            *args,
            statement=statement,
            **kwargs,
        )
        if result and call_load:
            await self.batch_load([result])
        return result

    async def get(
        self,
        item_id: Any,
        user: models.User | None = None,
        *args: Any,
        atomic_update: bool = False,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_load: bool = True,
        **kwargs: Any,
    ) -> ModelType:
        return cast(
            ModelType,
            await self._execute_get(
                self.repository.get_one,
                item_id,
                user,
                *args,
                atomic_update=atomic_update,
                statement=statement,
                filters=filters,
                call_load=call_load,
                **kwargs,
            ),
        )

    async def get_or_none(
        self,
        item_id: Any,
        user: models.User | None = None,
        *args: Any,
        atomic_update: bool = False,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_load: bool = True,
        **kwargs: Any,
    ) -> ModelType | None:
        return await self._execute_get(
            self.repository.get_one_or_none,
            item_id,
            user,
            *args,
            atomic_update=atomic_update,
            statement=statement,
            filters=filters,
            call_load=call_load,
            **kwargs,
        )

    async def list_and_count(
        self,
        *filters: StatementFilter | ColumnElement[bool],
        user: models.User | None = None,
        statement: Select[tuple[ModelType]] | None = None,
        call_load: bool = True,
        **kwargs: Any,
    ) -> tuple[list[ModelType], int]:
        filter_list = list(filters)
        self._add_user_filter(filter_list, user)
        try:
            results, count = await self.repository.list_and_count(
                *filter_list,
                statement=statement,
                **kwargs,
            )
        except ProgrammingError as e:
            if (
                e.orig
                and hasattr(e.orig, "sqlstate")
                and (len(e.orig.sqlstate) == 5 and (e.orig.sqlstate.startswith("42") or e.orig.sqlstate.startswith("22")))
            ):
                return [], 0
            raise
        if call_load:
            await self.batch_load(results)
        return results, count

    async def count(
        self,
        *filters: StatementFilter | ColumnElement[bool],
        user: models.User | None = None,
        statement: Select[tuple[ModelType]] | None = None,
        **kwargs: Any,
    ) -> int:
        filter_list = list(filters)
        self._add_user_filter(filter_list, user)
        try:
            return await self.repository.count(*filter_list, statement=statement, **kwargs)
        except NoResultFound:
            return 0

    @classmethod
    def apply_pagination_joins(
        cls, pagination: SearchPagination, statement: StatementTypeT, model: type[ModelProtocol]
    ) -> StatementTypeT:
        return statement

    @classmethod
    def apply_ordering(
        cls, query: Select[tuple[ModelType]], pagination: SearchPagination, model: type[ModelProtocol]
    ) -> Select[tuple[ModelType]]:
        allowed_columns = {col.key for col in model.__mapper__.columns}
        sort_col = pagination.sort
        if sort_col not in allowed_columns:
            return query.where(false())
        col_attr = utils.common.get_sqla_attr(cast(ModelProtocol, model), sort_col)
        order_expr = col_attr.desc() if pagination.desc else col_attr.asc()
        return query.order_by(order_expr)

    @classmethod
    def apply_pagination(
        cls, pagination: SearchPagination, statement: StatementTypeT, model: type[ModelProtocol], count_only: bool = False
    ) -> StatementTypeT:
        if isinstance(statement, Select):
            query = statement
            query = cls.apply_pagination_joins(pagination, query, model)
            queries = cls.pagination_search(pagination, model)
            # NOTE: for some reason mypy update caused it to complain here
            query = query.where(queries) if queries is not None else query  # type: ignore[assignment] # sqlalchemy core requires explicit checks
            if count_only:
                return query
            query = query.group_by(utils.common.get_sqla_attr(cast(ModelProtocol, model), "id"))  # type: ignore[assignment]
            if pagination.limit != -1:
                query = query.limit(pagination.limit)  # type: ignore[assignment]
            query = cls.apply_ordering(query, pagination, model)  # type: ignore[assignment]
            return query.offset(pagination.offset)  # type: ignore[return-value]
        return statement

    @classmethod
    def get_pagination_search_models(cls, model: type[ModelType]) -> list[type[ModelProtocol]]:
        return [model]

    @classmethod
    def pagination_search(cls, pagination: SearchPagination, model: type[ModelProtocol]) -> ColumnElement[bool] | None:
        if not pagination.query:
            return None
        queries = []
        queries.extend(pagination.query.get_created_filter(model))
        for search_filter, value in pagination.query.filters.items():
            column = getattr(model, search_filter, None)
            if column is not None:
                queries.append(column.in_(value))
        if hasattr(model, "meta"):
            meta_column = utils.common.get_sqla_attr(cast(ModelProtocol, model), "meta")
            for field_name, value in pagination.query.metadata_filters.items():
                queries.append(meta_column[field_name].astext.in_(value))
        full_filters = []
        for search_model in cls.get_pagination_search_models(cast(type[ModelType], model)):
            full_filters.extend(cls.get_pagination_all_columns_filter(search_model, pagination.query.text))
        queries.append(or_(*full_filters))
        return and_(*queries)

    @staticmethod
    def get_pagination_all_columns_filter(model: type[ModelProtocol], text: str) -> list[ColumnElement[bool]]:
        return [column.cast(Text).op("~*")(text) for column in model.__mapper__.columns]

    async def apply_pagination_filters(
        self, pagination: SearchPagination, statement: Select[tuple[ModelType]], request: Request
    ) -> Select[tuple[ModelType]]:
        from api.services.plugin_registry import PluginRegistry

        plugin_registry = await self.container.get(PluginRegistry)
        return await plugin_registry.apply_filters(
            "search_query", statement, self.model_type, dict(request.query_params), self, pagination.query
        )

    async def paginated_list_and_count(
        self,
        request: Request,
        pagination: SearchPagination,
        *,
        user: models.User | None = None,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        count_only: bool = False,
    ) -> tuple[list[ModelType], int]:
        statement = select(self.model_type) if statement is None else statement
        statement = self.apply_pagination(pagination, statement, self.model_type, count_only=count_only)
        statement = await self.apply_pagination_filters(pagination, statement, request)
        if count_only:
            return [], await self.count(*(filters or []), statement=statement, user=user)
        items, total = await self.list_and_count(
            *(filters or []),
            statement=statement,
            user=user,
            call_load=not pagination.autocomplete,
            load=[] if pagination.autocomplete else None,
        )
        return items, total

    async def paginate(
        self,
        request: Request,
        pagination: SearchPagination,
        *,
        user: models.User | None = None,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
    ) -> dict[str, Any] | JSONResponse:
        from api.utils.routing import prepare_autocomplete_response, prepare_pagination_response

        items, total = await self.paginated_list_and_count(
            request, pagination, user=user, statement=statement, filters=filters
        )
        if pagination.autocomplete:
            return prepare_autocomplete_response(items, request, pagination, total)
        return prepare_pagination_response(items, request, pagination, total)

    async def load_one(self, item: ModelType) -> None:
        pass

    async def merge_object(self, item: ModelType) -> ModelType:
        item = await self.session.merge(item)
        await self.load_one(item)
        return item

    async def batch_load(self, items: list[ModelType]) -> list[ModelType]:
        for item in items:
            await self.load_one(item)
        return items

    async def create(
        self, data: "ModelDictT[ModelType]", user: models.User | None = None, *, call_hooks: bool = True
    ) -> ModelType:
        from api.services.plugin_registry import PluginRegistry

        data = self._check_data(data, update=False)
        data = await self.prepare_data(data)
        data = await self.prepare_create(data, user)
        model = self.model_type(**data)
        await self.validate_create(data, model, user)
        result = await self.finalize_create(data, user)
        if call_hooks:
            plugin_registry = await self.container.get(PluginRegistry)
            await plugin_registry.run_hook(f"db_create_{self.model_type.__name__.lower()}", result)
        return result

    async def create_base(self, model: ModelType) -> ModelType:
        self.session.add(model)
        await self.session.flush()
        load_attributes = list(self.model_type.__mapper__.relationships.keys())
        await self.session.refresh(model, attribute_names=load_attributes)
        await self.batch_load([model])
        return model

    @overload
    async def update(
        self,
        data: "ModelDictT[ModelType]",
        item: ModelType,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType: ...

    @overload
    async def update(
        self,
        data: "ModelDictT[ModelType]",
        item: str,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType: ...

    async def update(
        self,
        data: "ModelDictT[ModelType]",
        item: ModelType | str,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType:
        from api.services.plugin_registry import PluginRegistry

        model = await self.get(item, user, statement=statement, filters=filters) if isinstance(item, str) else item
        mapper = sqla_inspect(model).mapper  # type: ignore[union-attr]
        old_model_data = {c.key: getattr(model, c.key) for c in mapper.column_attrs}
        old_model = self.model_type(**old_model_data)
        data = self._check_data(data, update=True)
        data = await self.prepare_data(data)
        await self.validate_update(data, model, user)
        data = await self.prepare_update(data, model)
        for attr, value in data.items():
            setattr(model, attr, value)
        await self.session.flush()
        if call_hooks:
            plugin_registry = await self.container.get(PluginRegistry)
            await plugin_registry.run_hook(f"db_modify_{self.model_type.__name__.lower()}", model, old_model)
        return model

    @overload
    async def delete(
        self,
        item: ModelType,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType: ...
    @overload
    async def delete(
        self,
        item: str,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType: ...
    async def delete(
        self,
        item: ModelType | str,
        user: models.User | None = None,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        call_hooks: bool = True,
    ) -> ModelType:
        from api.services.plugin_registry import PluginRegistry

        item = await self.get(item, user, statement=statement, filters=filters) if isinstance(item, str) else item
        await self.validate_delete(item, user)
        await self.session.delete(item)
        if call_hooks:
            plugin_registry = await self.container.get(PluginRegistry)
            await plugin_registry.run_hook(f"db_delete_{self.model_type.__name__.lower()}", item)
        return item

    async def delete_many(
        self,
        ids: list[str],
        user: models.User | None = None,
        *,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
        **kwargs: Any,
    ) -> list[ModelType]:
        filters_list: list[StatementFilter | ColumnElement[bool]] = [
            utils.common.get_sqla_attr(cast(ModelType, self.model_type), "id").in_(ids)
        ]
        if filters:
            filters_list.extend(filters)
        self._add_user_filter(filters_list, user)
        return list(await self.repository.delete_where(*filters_list, **kwargs))

    async def prepare_create(self, data: dict[str, Any], user: models.User | None = None) -> dict[str, Any]:
        return data

    async def finalize_create(self, data: dict[str, Any], user: models.User | None = None) -> ModelType:
        model = self.model_type(**data)
        return await self.create_base(model)

    async def prepare_update(self, data: dict[str, Any], model: ModelType) -> dict[str, Any]:
        return data

    async def _process_many_to_many_field(self, data: dict[str, Any], field_key: str, repository: CRUDRepository[Any]) -> None:
        field_ids = data.pop(field_key, None)
        if field_ids is not None:
            filters = [repository.model_type.id.in_(field_ids)]
            if "user_id" in data:
                filters.append(repository.model_type.user_id == data["user_id"])
            data[field_key] = await repository.list(*filters)
            if len(data[field_key]) != len(field_ids):
                raise unauthorized_access_exception()

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        if "metadata" in data:  # Map to sqlalchemy format
            data["meta"] = data.pop("metadata")
        return data

    @classmethod
    def _get_related_table_name(cls, col: ColumnElement[Any]) -> str:
        return cls.FKEY_MAPPING.get(col.name, col.name.replace("_id", "").capitalize())

    async def set_user_id(self, data: dict[str, Any], model: ModelType, user: models.User | None = None) -> str | None:
        if user is not None and hasattr(self.model_type, "user_id"):
            data["user_id"] = utils.common.get_sqla_attr(user, "id")
        return data.get("user_id")

    async def validate_m2m(self, related_model: type[ModelProtocol], related_ids: list[str], user_id: str | None) -> None:
        if not hasattr(related_model, "id"):
            return
        query = select(related_model).where(related_model.id.in_(related_ids))
        if hasattr(related_model, "user_id") and user_id is not None:
            query = query.where(related_model.user_id == user_id)
        count = cast(int, await utils.database.get_scalar(self.session, query, func.count, related_model.id))
        if count != len(related_ids):
            raise unauthorized_access_exception()

    async def validate(
        self, action: CRUDAction, data: dict[str, Any], model: ModelType, user: models.User | None = None
    ) -> None:
        user_id = await self.set_user_id(data, model, user)
        fkey_columns = (col for col in model.__table__.columns if col.foreign_keys)
        for col in fkey_columns:
            if col.name in data and data[col.name] is not None:
                # we assume i.e. user_id -> User
                table_name = self._get_related_table_name(col)
                current_model = models.all_tables[table_name]
                query = select(current_model).where(
                    utils.common.get_sqla_attr(cast(ModelType, current_model), "id") == data[col.name]
                )
                if hasattr(current_model, "user_id") and user_id is not None:
                    query = query.where(current_model.user_id == user_id)
                if not (await self.session.execute(query)).scalar_one_or_none():
                    raise unauthorized_access_exception()

        for rel in self.model_type.__mapper__.relationships:
            if rel.secondary is not None and rel.key in data:
                related_ids = [x.id for x in data[rel.key]]
                related_model = rel.entity.class_
                await self.validate_m2m(related_model, related_ids, user_id)

    async def validate_create(self, data: dict[str, Any], model: ModelType, user: models.User | None = None) -> None:
        await self.validate(CRUDAction.CREATE, data, model, user)

    async def validate_update(self, data: dict[str, Any], model: ModelType, user: models.User | None = None) -> None:
        await self.validate(CRUDAction.UPDATE, data, model, user)

    async def validate_delete(self, model: ModelType, user: models.User | None = None) -> None:
        await self.validate(CRUDAction.DELETE, {}, model, user)

    @property
    def supported_batch_actions(self) -> list[str]:
        return ["delete"]

    async def update_many(self, query: Update, ids: list[str], user: models.User | None = None) -> None:
        filters: list[StatementFilter | ColumnElement[bool]] = [
            utils.common.get_sqla_attr(cast(ModelType, self.model_type), "id").in_(ids)
        ]
        self._add_user_filter(filters, user)
        for filter_q in filters:
            query = query.where(cast(ColumnExpressionArgument[bool], filter_q))
        await self.session.execute(query)

    async def process_batch_action(
        self,
        settings: BatchAction,
        user: models.User,
        *,
        statement: Select[tuple[ModelType]] | None = None,
        filters: list[StatementFilter | ColumnElement[bool]] | None = None,
    ) -> bool:
        if settings.command not in self.supported_batch_actions:
            raise HTTPException(status_code=404, detail="Batch command not found")
        if settings.command == "delete":
            await self.delete_many(settings.ids, user, filters=filters)
        return True


type TService = CRUDService[Any]

__all__ = ["CRUDRepository", "CRUDService", "CRUDAction", "TService", "ModelDictT", "LoadSpec", "StatementTypeT"]
