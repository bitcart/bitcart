from typing import Annotated, Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from api import models, utils
from api.constants import AuthScopes
from api.schemas.auth import AuthResponse, FIDO2Auth, TOTPAuth
from api.schemas.tokens import EditToken, HTTPCreateLoginToken, Token
from api.services.crud.tokens import TokenService
from api.utils.routing import (
    OffsetPagination,
    SearchPagination,
    prepare_autocomplete_response,
    prepare_pagination_response,
    provide_pagination,
)

router = APIRouter(route_class=DishkaRoute)


@router.post("", response_model=AuthResponse)
async def create_token(
    token_service: FromDishka[TokenService],
    token_data: HTTPCreateLoginToken | None = None,
    auth_data: tuple[models.User | None, models.Token] | None = Security(
        utils.authorization.AuthDependency(token_required=False, return_token=True)
    ),
) -> Any:
    return await token_service.create_token(auth_data, token_data)


@router.post("/oauth2")
async def create_oauth2_token(
    token_service: FromDishka[TokenService],
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_data: tuple[models.User | None, models.Token] | None = Security(
        utils.authorization.AuthDependency(token_required=False, return_token=True)
    ),
) -> Any:
    try:
        token_data = HTTPCreateLoginToken(email=form_data.username, password=form_data.password, permissions=form_data.scopes)
    except ValidationError as e:
        raise HTTPException(422, e.errors()) from None
    return await token_service.create_token(auth_data, token_data)


@router.post("/2fa/totp")
async def create_token_totp_auth(token_service: FromDishka[TokenService], auth_data: TOTPAuth) -> Any:
    return await token_service.create_token_totp_auth(auth_data)


@router.post("/2fa/fido2/begin")
async def create_token_fido2_begin(token_service: FromDishka[TokenService], auth_data: FIDO2Auth) -> Any:  # pragma: no cover
    return await token_service.create_token_fido2_begin(auth_data)


@router.post("/2fa/fido2/complete")
async def create_token_fido2_complete(token_service: FromDishka[TokenService], request: Request) -> Any:  # pragma: no cover
    return await token_service.create_token_fido2_complete(request)


@router.delete("/{token_id}", response_model=Token)
async def delete_token(
    token_service: FromDishka[TokenService],
    token_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:
    return await token_service.delete(token_id, user)


@router.get("", response_model=OffsetPagination[Token])
async def get_tokens(
    pagination: Annotated[SearchPagination, Depends(provide_pagination)],
    token_service: FromDishka[TokenService],
    request: Request,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
    app_id: str | None = None,
    redirect_url: str | None = None,
    permissions: list[str] = Query(None),
) -> Any:
    statement, filters = token_service._filter_in_token(app_id, redirect_url, permissions)
    items, total = await token_service.list_and_count(
        pagination, *filters, statement=statement, user=user, call_load=not pagination.autocomplete
    )
    if pagination.autocomplete:
        return prepare_autocomplete_response(items, request, pagination, total)
    return prepare_pagination_response(items, request, pagination, total)


# TODO: improve it somehow? e.g. move to identity provider
@router.get("/current", response_model=Token)
async def get_current_token(
    auth_data: tuple[models.User, str] = Security(utils.authorization.AuthDependency(return_token=True)),
) -> Any:
    return auth_data[1]


@router.get("/count", response_model=int)
async def get_token_count(
    token_service: FromDishka[TokenService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
    app_id: str | None = None,
    redirect_url: str | None = None,
    permissions: list[str] = Query(None),
) -> Any:
    statement, filters = token_service._filter_in_token(app_id, redirect_url, permissions)
    return await token_service.count(*filters, statement=statement, user=user)


@router.patch("/{model_id}", response_model=Token)
async def patch_token(
    token_service: FromDishka[TokenService],
    model_id: str,
    model: EditToken,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:
    return await token_service.update(model, model_id, user)
