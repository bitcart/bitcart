from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, cast
from urllib import parse as urlparse

from advanced_alchemy.base import ModelProtocol
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends, Query, Request, Security
from fastapi.responses import JSONResponse

from api import models, utils
from api.constants import AuthScopes
from api.schemas.base import Schema
from api.schemas.misc import BatchAction
from api.utils.common import SearchQuery

if TYPE_CHECKING:
    from api.services.crud import TService


ModelT = TypeVar("ModelT", bound=ModelProtocol)


@dataclass
class SearchPagination:
    limit: int
    """Maximum number of rows to return."""
    offset: int
    """Number of rows to skip before returning results."""
    query: SearchQuery
    """Search query."""
    multiple: bool
    """Whether to return multiple results for search."""
    sort: str
    """Field to sort by."""
    desc: bool
    """Whether to sort in descending order."""
    autocomplete: bool
    """Whether to return minimal data for autocomplete."""


def provide_pagination(
    offset: int = Query(default=0, ge=0, le=None),
    limit: int = Query(default=5, ge=-1, le=1000),
    query: str = Query(default=""),
    multiple: bool = Query(default=False),
    sort: str = Query(default=""),
    desc: bool = Query(default=True),
    autocomplete: bool = Query(default=False),
) -> SearchPagination:
    """Dependency that provides enhanced pagination with search and sorting."""
    if multiple:
        query = query.replace(",", "|")
    search_query = SearchQuery(query)
    if not sort:
        sort = "created"
        desc = True
    return SearchPagination(
        limit=limit,
        offset=offset,
        query=search_query,
        multiple=multiple,
        sort=sort,
        desc=desc,
        autocomplete=autocomplete,
    )


type CreateSchemaT = Schema
type UpdateSchemaT = Schema
type DisplaySchemaT = Schema


@dataclass
class OffsetPagination[T]:
    """Container for data returned using limit/offset pagination."""

    __slots__ = ("result", "count", "previous", "next")

    result: Sequence[T]
    """List of data being sent as part of the response."""
    count: int
    """Total number of items."""
    previous: str | None
    """URL to the previous page."""
    next: str | None
    """URL to the next page."""


def noop_dependency() -> models.User | None:
    return None


def get_previous_url(request: Request, limit: int, offset: int) -> str | None:
    if limit == -1 or offset <= 0:
        return None
    if offset - limit <= 0:
        return str(request.url.remove_query_params(keys=["offset"]))
    return str(request.url.include_query_params(limit=limit, offset=offset - limit))


def get_next_url(request: Request, limit: int, offset: int, count: int) -> str | None:
    if limit == -1 or offset + limit >= count:
        return None
    return str(request.url.include_query_params(limit=limit, offset=offset + limit))


def prepare_autocomplete_response(
    items: list[Any], request: Request, pagination: SearchPagination, total: int
) -> JSONResponse:
    return JSONResponse(
        prepare_pagination_response(
            [{"id": item.id, "name": getattr(item, "name", item.id)} for item in items], request, pagination, total
        )
    )


def prepare_pagination_response(
    items: list[Any],
    request: Request,
    pagination: SearchPagination,
    total: int,
) -> dict[str, Any]:
    return {
        "result": items,
        "count": total,
        "previous": get_previous_url(request, pagination.limit, pagination.offset),
        "next": get_next_url(request, pagination.limit, pagination.offset, total),
    }


ALL_ENDPOINTS = ["list", "count", "get", "create", "update", "delete", "batch"]


def maybe_add_route(
    router: APIRouter, enabled_endpoints: dict[str, bool], endpoint: str, path: str, func: Any, **kwargs: Any
) -> None:
    if enabled_endpoints[endpoint]:
        router.add_api_route(path, func, **kwargs)


def create_crud_router(
    create_schema: type[CreateSchemaT],
    update_schema: type[UpdateSchemaT],
    display_schema: type[DisplaySchemaT],
    service_class: type["TService"],
    prefix: str = "",
    tags: list[str | Enum] | None = None,
    router: APIRouter | None = None,
    auth_config: dict[str, bool] | bool = True,
    disabled_endpoints: dict[str, bool] | None = None,
    required_scopes: list[str | AuthScopes] | None = None,
) -> APIRouter:
    if not TYPE_CHECKING:
        TService = service_class
        CreateSchemaT = create_schema
        UpdateSchemaT = utils.common.to_optional(update_schema)
        DisplaySchemaT = display_schema
    router = router or APIRouter(prefix=prefix, tags=tags or [], route_class=DishkaRoute)
    required_scopes = required_scopes or []
    if isinstance(auth_config, bool):
        auth_config = dict.fromkeys(ALL_ENDPOINTS, auth_config)
    else:
        default_auth_config = dict.fromkeys(ALL_ENDPOINTS, True)
        auth_config = {**default_auth_config, **auth_config}
    enabled_endpoints = dict.fromkeys(ALL_ENDPOINTS, True)
    if disabled_endpoints is not None:
        enabled_endpoints = {k: v and not disabled_endpoints.get(k, False) for k, v in enabled_endpoints.items()}
    auth_deps = {
        endpoint: Security(
            utils.authorization.auth_dependency if auth_config[endpoint] else utils.authorization.optional_auth_dependency,
            scopes=required_scopes,
        )
        for endpoint in ALL_ENDPOINTS
    }

    async def list_items(
        pagination: Annotated[SearchPagination, Depends(provide_pagination)],
        service: FromDishka[TService],
        request: Request,
        user: models.User | None = auth_deps["list"],
    ) -> Any:
        return await service.paginate(request, pagination, user=user)

    maybe_add_route(
        router, enabled_endpoints, "list", "", list_items, methods=["GET"], response_model=OffsetPagination[DisplaySchemaT]
    )

    async def get_count(
        service: FromDishka[TService],
        user: models.User | None = auth_deps["count"],
    ) -> int:
        return await service.count(user=user)

    maybe_add_route(router, enabled_endpoints, "count", "/count", get_count, methods=["GET"], response_model=int)

    async def get_item(
        item_id: str,
        service: FromDishka[TService],
        user: models.User | None = auth_deps["get"],
    ) -> Any:
        return await service.get(item_id, user)

    maybe_add_route(router, enabled_endpoints, "get", "/{item_id}", get_item, methods=["GET"], response_model=DisplaySchemaT)

    async def create_item(
        data: CreateSchemaT,
        service: FromDishka[TService],
        user: models.User | None = auth_deps["create"],
    ) -> Any:
        return await service.create(data, user)

    maybe_add_route(router, enabled_endpoints, "create", "", create_item, methods=["POST"], response_model=DisplaySchemaT)

    async def update_item(
        item_id: str,
        data: UpdateSchemaT,
        service: FromDishka[TService],
        user: models.User | None = auth_deps["update"],
    ) -> Any:
        return await service.update(data, item_id, user)

    maybe_add_route(
        router, enabled_endpoints, "update", "/{item_id}", update_item, methods=["PATCH"], response_model=DisplaySchemaT
    )

    async def delete_item(
        item_id: str,
        service: FromDishka[TService],
        user: models.User | None = auth_deps["delete"],
    ) -> Any:
        return await service.delete(item_id, user)

    maybe_add_route(
        router, enabled_endpoints, "delete", "/{item_id}", delete_item, methods=["DELETE"], response_model=DisplaySchemaT
    )

    async def batch_action(
        data: BatchAction,
        service: FromDishka[TService],
        user: models.User | None = auth_deps["batch"],
    ) -> bool:
        return await service.process_batch_action(data, cast(models.User, user))

    maybe_add_route(router, enabled_endpoints, "batch", "/batch", batch_action, methods=["POST"], response_model=bool)
    return router


def get_redirect_url(url: str, **kwargs: Any) -> str:
    parsed = urlparse.urlparse(url)
    query = parsed.query
    url_dict = dict(urlparse.parse_qs(query))
    for key, value in kwargs.items():
        if key not in url_dict:
            url_dict[key] = value
        else:
            url_dict[key].append(value)
    url_new_query = urlparse.urlencode(url_dict, doseq=True)
    parsed = parsed._replace(query=url_new_query)
    return urlparse.urlunparse(parsed)
