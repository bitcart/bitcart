import json
from typing import Any, cast

import pyotp
from advanced_alchemy.filters import StatementFilter
from dishka import AsyncContainer
from fastapi import HTTPException, Request
from fido2.server import Fido2Server
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity, UserVerificationRequirement
from sqlalchemy import ColumnElement, Select

from api import models, utils
from api.constants import FIDO2_LOGIN_KEY, SHORT_EXPIRATION
from api.db import AsyncSession
from api.redis import Redis
from api.schemas.auth import FIDO2Auth, TOTPAuth
from api.schemas.policies import Policy
from api.schemas.tokens import CreateDBToken, HTTPCreateLoginToken, Token
from api.services.auth import AuthService
from api.services.crud import CRUDService, ModelDictT
from api.services.crud.repositories import TokenRepository, UserRepository
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.types import TasksBroker

TFA_REDIS_KEY = "users_tfa"


class TokenService(CRUDService[models.Token]):
    repository_type = TokenRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        redis_pool: Redis,
        broker: TasksBroker,
        user_repository: UserRepository,
        auth_service: AuthService,
        setting_service: SettingService,
        plugin_registry: PluginRegistry,
    ) -> None:
        super().__init__(session, container)
        self.redis_pool = redis_pool
        self.broker = broker
        self.user_repository = user_repository
        self.auth_service = auth_service
        self.setting_service = setting_service
        self.plugin_registry = plugin_registry

    async def create_token(
        self,
        auth_data: tuple[models.User | None, models.Token] | None,
        token_data: HTTPCreateLoginToken | None = None,
    ) -> dict[str, Any]:
        if token_data is None:  # pragma: no cover
            token_data = HTTPCreateLoginToken()
        user, token = None, None
        if auth_data:
            user, token = auth_data
        checked_user = await self.validate_credentials(user, token_data)
        token_dict = token_data.model_dump()
        strict = token_dict.pop("strict")
        if "server_management" in token_dict["permissions"] and not checked_user.is_superuser:
            if strict:
                raise HTTPException(422, "This application requires access to server settings")
            token_dict["permissions"].remove("server_management")
        if token and "full_control" not in token.permissions:
            for permission in token_dict["permissions"]:
                if permission not in token.permissions:
                    raise HTTPException(403, "Not enough permissions")
        if not checked_user.is_enabled:
            raise HTTPException(403, "Account is disabled")
        policies = await self.setting_service.get_setting(Policy)
        if policies.require_verified_email and not checked_user.is_verified:
            raise HTTPException(403, "Email is not verified")
        token_scheme = CreateDBToken(**token_dict, user_id=checked_user.id).model_dump()
        requires_extra = not token and (checked_user.tfa_enabled or bool(checked_user.fido2_devices))
        if requires_extra:
            return await self.create_token_tfa_flow(token_scheme, checked_user)
        return await self.create_token_normal(token_scheme)

    async def create_token_totp_auth(self, auth_data: TOTPAuth) -> dict[str, Any]:
        token_data = await self.redis_pool.get(f"{TFA_REDIS_KEY}:{auth_data.token}")
        if token_data is None:
            raise HTTPException(422, "Invalid token")
        token_data = CreateDBToken(**json.loads(token_data))
        user = await self.user_repository.get_one_or_none(id=token_data.user_id)
        if not user:  # pragma: no cover
            raise HTTPException(422, "Invalid token")
        if auth_data.code not in user.recovery_codes and not pyotp.TOTP(user.totp_key).verify(auth_data.code.replace(" ", "")):
            raise HTTPException(422, "Invalid code")
        if auth_data.code in user.recovery_codes:
            user.recovery_codes.remove(auth_data.code)
        await self.redis_pool.delete(f"{TFA_REDIS_KEY}:{auth_data.token}")
        return await self.create_token_normal(token_data)

    async def validate_credentials(self, user: models.User | None | bool, token_data: HTTPCreateLoginToken) -> models.User:
        if not user:
            user, status = await self.auth_service.authenticate_user(token_data.email, token_data.password)
            if not user:
                raise HTTPException(401, {"message": "Unauthorized", "status": status})
            await self.auth_service.captcha_flow(token_data.captcha_code)
        return cast(models.User, user)

    async def create_token_normal(self, token_data: "ModelDictT[models.Token]") -> dict[str, Any]:
        token = await self.create(token_data)
        await self.plugin_registry.run_hook("token_created", token)
        return {
            **Token.model_validate(token).model_dump(),
            "access_token": token.id,
            "token_type": "bearer",
            "tfa_required": False,
            "tfa_code": None,
            "tfa_types": [],
        }

    async def create_token_tfa_flow(self, token_data: dict[str, Any], user: models.User) -> dict[str, Any]:
        code = utils.common.unique_id()
        await self.redis_pool.set(
            f"{TFA_REDIS_KEY}:{code}", CreateDBToken(**token_data).model_dump_json(), ex=SHORT_EXPIRATION
        )
        tfa_types = []
        if user.fido2_devices:  # pragma: no cover
            tfa_types.append("fido2")
        if user.tfa_enabled:
            tfa_types.append("totp")
        return {
            "access_token": None,
            "token_type": "bearer",
            "tfa_required": True,
            "tfa_code": code,
            "tfa_types": tfa_types,
        }

    @staticmethod
    def _filter_in_token(
        app_id: str | None = None,
        redirect_url: str | None = None,
        permissions: list[str] | None = None,
    ) -> tuple[Select[tuple[models.Token]] | None, list[StatementFilter | ColumnElement[bool]]]:
        filters: list[StatementFilter | ColumnElement[bool]] = []
        statement: Select[tuple[models.Token]] | None = None
        if app_id is not None:
            filters.append(models.Token.app_id == app_id)
        if redirect_url is not None:
            filters.append(models.Token.redirect_url == redirect_url)
        if permissions is not None:
            filters.append(models.Token.permissions.contains(permissions))
        return statement, filters

    async def logout_all(self, user: models.User) -> None:
        await self.repository.delete_where(models.Token.user_id == user.id)

    async def create_token_fido2_begin(self, auth_data: FIDO2Auth) -> dict[str, Any]:  # pragma: no
        token_data = await self.redis_pool.get(f"{TFA_REDIS_KEY}:{auth_data.token}")
        if token_data is None:
            raise HTTPException(422, "Invalid token")
        token_data = CreateDBToken(**json.loads(token_data))
        user = await self.user_repository.get_one_or_none(id=token_data.user_id)
        if not user:
            raise HTTPException(422, "Invalid token")
        existing_credentials = [AttestedCredentialData(bytes.fromhex(x["device_data"])) for x in user.fido2_devices]
        options, state = Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_data.auth_host)).authenticate_begin(
            existing_credentials, user_verification=UserVerificationRequirement.DISCOURAGED
        )
        await self.redis_pool.set(f"{FIDO2_LOGIN_KEY}:{user.id}", json.dumps(state), ex=SHORT_EXPIRATION)
        return dict(options)

    async def create_token_fido2_complete(self, request: Request) -> dict[str, Any]:  # pragma: no cover
        data = await request.json()
        if "token" not in data or "auth_host" not in data:
            raise HTTPException(422, "Missing name")
        auth_host = data["auth_host"]
        token_data = await self.redis_pool.get(f"{TFA_REDIS_KEY}:{data['token']}")
        if token_data is None:
            raise HTTPException(422, "Invalid token")
        token_data = CreateDBToken(**json.loads(token_data))
        user = await self.user_repository.get_one_or_none(id=token_data.user_id)
        if not user:
            raise HTTPException(422, "Invalid token")
        existing_credentials = [AttestedCredentialData(bytes.fromhex(x["device_data"])) for x in user.fido2_devices]
        state = await self.redis_pool.get(f"{FIDO2_LOGIN_KEY}:{user.id}")
        state = json.loads(state) if state else None
        try:
            Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_host)).authenticate_complete(
                state,
                existing_credentials,
                data,
            )
        except Exception as e:
            raise HTTPException(422, str(e)) from None
        await self.redis_pool.delete(f"{FIDO2_LOGIN_KEY}:{user.id}")
        await self.redis_pool.delete(f"{TFA_REDIS_KEY}:{data['token']}")
        return await self.create_token_normal(token_data)
