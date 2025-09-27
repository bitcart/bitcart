from fastapi import HTTPException, Request
from fastapi.security import SecurityScopes
from sqlalchemy.orm import joinedload
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from api import models, utils
from api.db import AsyncSession
from api.schemas.misc import CaptchaType
from api.schemas.policies import Policy
from api.services.crud.repositories import TokenRepository, UserRepository
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.types import PasswordHasherProtocol


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        token_repository: TokenRepository,
        password_hasher: PasswordHasherProtocol,
        setting_service: SettingService,
        plugin_registry: PluginRegistry,
    ) -> None:
        self.session = session
        self.user_repository = user_repository
        self.token_repository = token_repository
        self.password_hasher = password_hasher
        self.setting_service = setting_service
        self.plugin_registry = plugin_registry

    async def authenticate_user(self, email: str, password: str) -> tuple[models.User | bool, int]:
        user = await self.user_repository.get_one_or_none(email=email)
        if not user:
            return False, 404
        if not self.password_hasher.verify_password(password, user.hashed_password):
            return False, 401
        return user, 200

    async def find_by_token(self, token: str) -> tuple[models.User, models.Token] | None:
        result = await self.token_repository.get_one_or_none(id=token, load=[joinedload(models.Token.user)])
        if not result:
            return None
        return result.user, result

    async def find_user_and_check_permissions(
        self,
        header_token: str | None,
        security_scopes: SecurityScopes,
        request: Request | None = None,
    ) -> tuple[models.User, models.Token]:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"' if security_scopes.scopes else "Bearer"
        exc = HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
        if not header_token:
            raise exc
        data = await self.find_by_token(header_token)
        if data is None:
            raise exc
        user, token = data
        await self.check_permissions(user, token, security_scopes, request, authenticate_value)
        return user, token

    async def check_permissions(
        self,
        user: models.User,
        token: models.Token,
        security_scopes: SecurityScopes,
        request: Request | None,
        authenticate_value: str,
    ) -> None:
        if not user.is_enabled:
            raise HTTPException(403, "Account is disabled")
        forbidden_exception = HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )
        if "full_control" not in token.permissions:
            for auth_scope in security_scopes.scopes:
                scope = str(auth_scope)
                if scope not in utils.authorization.get_all_scopes():
                    raise ValueError(f"Invalid scope: {scope}")
                if scope not in token.permissions and not self.check_selective_scopes(request, scope, token):
                    await self.plugin_registry.run_hook("permission_denied", user, token, scope)
                    raise forbidden_exception
        if "server_management" in security_scopes.scopes and not user.is_superuser:
            await self.plugin_registry.run_hook("permission_denied", user, token, "server_management")
            raise forbidden_exception
        await self.plugin_registry.run_hook("permission_granted", user, token, security_scopes.scopes)

    @staticmethod
    def check_selective_scopes(
        request: Request | None,
        scope: str,
        token: models.Token,
    ) -> bool:
        if request is None:
            return False
        model_id = request.path_params.get("model_id", None)
        if model_id is None:
            return False
        return f"{scope}:{model_id}" in token.permissions

    async def verify_captcha(self, api_uri: str, code: str, secret: str) -> bool:
        try:
            return (await utils.common.send_request("POST", api_uri, data={"response": code, "secret": secret}))["success"]
        except Exception:  # pragma: no cover
            return False

    async def captcha_flow(self, code: str) -> None:
        policies = await self.setting_service.get_setting(Policy)
        if policies.captcha_type != CaptchaType.NONE:  # pragma: no cover
            if policies.captcha_type == CaptchaType.HCAPTCHA:
                api_uri = "https://hcaptcha.com/siteverify"
            elif policies.captcha_type == CaptchaType.CF_TURNSTILE:
                api_uri = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
            if not await self.verify_captcha(api_uri, code, policies.captcha_secretkey):
                await self.plugin_registry.run_hook("captcha_failed")
                raise HTTPException(401, {"message": "Unauthorized", "status": 403})
            await self.plugin_registry.run_hook("captcha_passed")
