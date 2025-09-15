from collections.abc import Awaitable, Callable
from typing import Any, cast

from advanced_alchemy.base import ModelProtocol
from advanced_alchemy.filters import StatementFilter
from advanced_alchemy.repository import LoadSpec, SQLAlchemyAsyncRepository
from advanced_alchemy.service.typing import ModelDictT
from fastapi import HTTPException
from sqlalchemy import ColumnElement, ColumnExpressionArgument, Select, Update, func, select
from sqlalchemy.exc import NoResultFound, ProgrammingError

from api import models, utils
from api.db import AsyncSession
from api.schemas.base import Schema
from api.schemas.misc import BatchAction

UNAUTHORIZED_ACCESS_EXCEPTION = HTTPException(403, "Access denied: attempt to use objects not owned by current user")


class CRUDRepository[ModelType: ModelProtocol](SQLAlchemyAsyncRepository[ModelType]):
    def __init__(self, session: AsyncSession, *args: Any, **kwargs: Any) -> None:
        kwargs["wrap_exceptions"] = False
        kwargs["uniquify"] = True
        super().__init__(*args, session=session, **kwargs)


class CRUDService[ModelType: ModelProtocol]:
    session: AsyncSession
    repository_type: type[CRUDRepository[ModelType]]

    LOAD_OPTIONS: LoadSpec | None = None

    @property
    def model_type(self) -> type[ModelType]:
        return self.repository_type.model_type

    def _check_data(self, data: "ModelDictT[ModelType]", update: bool = False) -> dict[str, Any]:
        if isinstance(data, Schema):
            data = data.model_dump(exclude_unset=update)
        if not isinstance(data, dict):
            raise ValueError("CRUDService doesn't support non-dict data")
        return data

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = self.repository_type(session=session, load=self.LOAD_OPTIONS)

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
        **kwargs: Any,
    ) -> ModelType | None:
        filters = (
            [utils.common.get_sqla_attr(cast(ModelType, self.model_type), "id") == item_id] if item_id is not None else []
        )
        self._add_user_filter(filters, user)
        if statement is None:
            statement = select(self.model_type)
        if atomic_update:
            statement = statement.with_for_update()
        result = await method(
            *filters,
            *args,
            statement=statement,
            **kwargs,
        )
        if result:
            await self.batch_load([result])
        return result

    async def get(
        self,
        item_id: Any,
        user: models.User | None = None,
        *args: Any,
        atomic_update: bool = False,
        statement: Select[tuple[ModelType]] | None = None,
        **kwargs: Any,
    ) -> ModelType:
        return cast(
            ModelType,
            await self._execute_get(
                self.repository.get_one, item_id, user, *args, atomic_update=atomic_update, statement=statement, **kwargs
            ),
        )

    async def get_or_none(
        self,
        item_id: Any,
        user: models.User | None = None,
        *args: Any,
        atomic_update: bool = False,
        statement: Select[tuple[ModelType]] | None = None,
        **kwargs: Any,
    ) -> ModelType | None:
        return await self._execute_get(
            self.repository.get_one_or_none, item_id, user, *args, atomic_update=atomic_update, statement=statement, **kwargs
        )

    async def list_and_count(
        self,
        *filters: StatementFilter | ColumnElement[bool],
        user: models.User | None = None,
        statement: Select[tuple[ModelType]] | None = None,
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
        await self.batch_load(results)
        return results, count

    async def count(
        self, *filters: StatementFilter | ColumnElement[bool], user: models.User | None = None, **kwargs: Any
    ) -> int:
        filter_list = list(filters)
        self._add_user_filter(filter_list, user)
        try:
            return await self.repository.count(*filter_list, **kwargs)
        except NoResultFound:
            return 0

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

    async def create(self, data: "ModelDictT[ModelType]", user: models.User | None = None) -> ModelType:
        data = self._check_data(data, update=False)
        data = await self.prepare_data(data)
        data = await self.prepare_create(data, user)
        model = self.model_type(**data)
        await self.validate(data, model, user)
        return await self.finalize_create(data, user)

    async def create_base(self, model: ModelType) -> ModelType:
        self.session.add(model)
        await self.session.flush()
        load_attributes = list(self.model_type.__mapper__.relationships.keys())
        await self.session.refresh(model, attribute_names=load_attributes)
        await self.batch_load([model])
        return model

    async def update(self, data: "ModelDictT[ModelType]", item_id: str, user: models.User | None = None) -> ModelType:
        model = await self.get(item_id, user)
        data = self._check_data(data, update=True)
        data = await self.prepare_data(data)
        await self.validate(data, model, user)
        data = await self.prepare_update(data, model)
        for attr, value in data.items():
            setattr(model, attr, value)
        await self.session.flush()
        return model

    async def delete(self, item_id: str, user: models.User | None = None) -> ModelType:
        item = await self.get(item_id, user)
        await self.session.delete(item)
        return item

    async def delete_many(self, ids: list[str], user: models.User | None = None) -> list[ModelType]:
        filters: list[StatementFilter | ColumnElement[bool]] = [
            utils.common.get_sqla_attr(cast(ModelType, self.model_type), "id").in_(ids)
        ]
        self._add_user_filter(filters, user)
        return list(await self.repository.delete_where(*filters))

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
                raise UNAUTHORIZED_ACCESS_EXCEPTION

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        if "metadata" in data:  # Map to sqlalchemy format
            data["meta"] = data.pop("metadata")
        return data

    @staticmethod
    def _get_related_table_name(col: ColumnElement[Any]) -> str:
        return col.name.replace("_id", "") + "s"

    async def set_user_id(self, data: dict[str, Any], model: ModelType, user: models.User | None = None) -> str | None:
        if user is not None and hasattr(self.model_type, "user_id"):
            data["user_id"] = utils.common.get_sqla_attr(user, "id")
        return data.get("user_id")

    async def validate_m2m(self, related_model: type[ModelProtocol], related_ids: list[str], user_id: str | None) -> None:
        if not hasattr(related_model, "id"):
            return
        query = select(related_model).where(related_model.id.in_(related_ids))
        if hasattr(related_model, "user_id"):
            query = query.where(related_model.user_id == user_id)
        count = cast(int, await utils.database.get_scalar(self.session, query, func.count, related_model.id))
        if count != len(related_ids):
            raise UNAUTHORIZED_ACCESS_EXCEPTION

    async def validate(self, data: dict[str, Any], model: ModelType, user: models.User | None = None) -> None:
        user_id = await self.set_user_id(data, model, user)
        fkey_columns = (col for col in model.__table__.columns if col.foreign_keys)
        for col in fkey_columns:
            if col.name in data:
                # we assume i.e. user_id -> User
                table_name = self._get_related_table_name(col)
                current_model = models.all_tables[table_name]
                query = select(current_model).where(current_model.id == data[col.name])
                if hasattr(current_model, "user_id"):
                    query = query.where(current_model.user_id == user_id)
                if not (await self.session.execute(query)).scalar_one_or_none():
                    raise UNAUTHORIZED_ACCESS_EXCEPTION

        for rel in self.model_type.__mapper__.relationships:
            if rel.secondary is not None and rel.key in data:
                related_ids = [x.id for x in data[rel.key]]
                related_model = rel.entity.class_
                await self.validate_m2m(related_model, related_ids, user_id)

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

    async def process_batch_action(self, settings: BatchAction, user: models.User) -> bool:
        if settings.command not in self.supported_batch_actions:
            raise HTTPException(status_code=404, detail="Batch command not found")
        if settings.command == "delete":
            await self.delete_many(settings.ids, user)
        return True


type TService = CRUDService[Any]

__all__ = ["CRUDRepository", "CRUDService", "TService", "ModelDictT"]
