import json
from typing import List, Optional

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import SecurityScopes
from starlette.requests import Request

from api import models, pagination, schemes, settings, utils
from api.constants import SHORT_EXPIRATION
from api.plugins import run_hook

router = APIRouter()

TFA_REDIS_KEY = "users_tfa"


@router.get("", response_model=utils.routing.get_pagination_model(schemes.Token))
async def get_tokens(
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
    pagination: pagination.Pagination = Depends(),
    app_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    permissions: List[str] = Query(None),
):
    return await utils.database.paginate_object(
        models.Token, pagination, user, app_id=app_id, redirect_url=redirect_url, permissions=permissions
    )


@router.get("/current", response_model=schemes.Token)
async def get_current_token(request: Request):
    _, token = await utils.authorization.AuthDependency()(request, SecurityScopes(), return_token=True)
    return token


@router.get("/count", response_model=int)
async def get_token_count(
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
    pagination: pagination.Pagination = Depends(),
    app_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    permissions: List[str] = Query(None),
):
    return await utils.database.paginate_object(
        models.Token, pagination, user, app_id=app_id, redirect_url=redirect_url, permissions=permissions, count_only=True
    )


@router.patch("/{model_id}", response_model=schemes.Token)
async def patch_token(
    model_id: str,
    model: schemes.EditToken,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):
    item = await utils.database.get_object(
        models.Token,
        model_id,
        custom_query=models.Token.query.where(models.Token.user_id == user.id).where(models.Token.id == model_id),
    )
    await utils.database.modify_object(item, model.dict(exclude_unset=True))
    return item


@router.delete("/{model_id}", response_model=schemes.Token)
async def delete_token(
    model_id: str,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):
    item = await utils.database.get_object(
        models.Token,
        model_id,
        custom_query=models.Token.query.where(models.Token.user_id == user.id).where(models.Token.id == model_id),
    )
    await item.delete()
    return item


async def validate_credentials(request, token_data):
    token = None
    try:
        user, token = await utils.authorization.AuthDependency()(request, SecurityScopes(), return_token=True)
    except HTTPException:
        user, status = await utils.authorization.authenticate_user(token_data.email, token_data.password)
        if not user:
            raise HTTPException(401, {"message": "Unauthorized", "status": status})
    if not token:
        await utils.authorization.captcha_flow(token_data.captcha_code)
    return user, token


@router.post("")
async def create_token(
    request: Request,
    token_data: Optional[schemes.HTTPCreateLoginToken] = schemes.HTTPCreateLoginToken(),
):
    user, token = await validate_credentials(request, token_data)
    token_data = token_data.dict()
    strict = token_data.pop("strict")
    if "server_management" in token_data["permissions"] and not user.is_superuser:
        if strict:
            raise HTTPException(422, "This application requires access to server settings")
        token_data["permissions"].remove("server_management")
    if token and "full_control" not in token.permissions:
        for permission in token_data["permissions"]:
            if permission not in token.permissions:
                raise HTTPException(403, "Not enough permissions")
    if user.tfa_enabled:
        async with utils.redis.wait_for_redis():
            code = utils.common.unique_id()
            await settings.settings.redis_pool.set(
                f"{TFA_REDIS_KEY}:{code}", schemes.CreateDBToken(**token_data, user_id=user.id).json(), ex=SHORT_EXPIRATION
            )
    else:
        token = await utils.database.create_object(models.Token, schemes.CreateDBToken(**token_data, user_id=user.id))
        await run_hook("token_created", token)
    return {
        **(schemes.Token.from_orm(token).dict() if not user.tfa_enabled else {}),
        "access_token": token.id if not user.tfa_enabled else None,
        "token_type": "bearer",
        "tfa_required": user.tfa_enabled,
        "tfa_code": code if user.tfa_enabled else None,
    }


@router.post("/2fa/totp")
async def create_token_totp_auth(auth_data: schemes.TOTPAuth):
    async with utils.redis.wait_for_redis():
        token_data = await settings.settings.redis_pool.get(f"{TFA_REDIS_KEY}:{auth_data.token}")
    if token_data is None:
        raise HTTPException(422, "Invalid token")
    token_data = schemes.CreateDBToken(**json.loads(token_data))
    user = await utils.database.get_object(models.User, token_data.user_id, raise_exception=False)
    if not user:
        raise HTTPException(422, "Invalid token")
    if auth_data.code not in user.recovery_codes and not pyotp.TOTP(user.totp_key).verify(auth_data.code.replace(" ", "")):
        raise HTTPException(422, "Invalid code")
    if auth_data.code in user.recovery_codes:
        user.recovery_codes.remove(auth_data.code)
        await user.update(recovery_codes=user.recovery_codes).apply()
    token = await utils.database.create_object(models.Token, token_data)
    await run_hook("token_created", token)
    return {
        **schemes.Token.from_orm(token).dict(),
        "access_token": token.id,
        "token_type": "bearer",
        "tfa_required": False,
        "tfa_code": None,
    }
