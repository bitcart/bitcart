import json
from typing import Any, cast
from urllib.parse import urlsplit

from aiohttp import ClientTimeout
from fastapi import HTTPException, Request
from fastapi.security import SecurityScopes
from sqlalchemy.orm import joinedload
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from api import models, utils
from api.constants import CAPTCHA_TIMEOUT, AuthScopes, CaptchaAction
from api.db import AsyncSession
from api.logging import get_exception_message, get_logger
from api.schemas.misc import CaptchaType
from api.schemas.policies import Policy
from api.services.crud.repositories import TokenRepository, UserRepository
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.types import PasswordHasherProtocol

logger = get_logger(__name__)

CAPTCHA_URLS: dict[str, str] = {
    CaptchaType.HCAPTCHA: "https://api.hcaptcha.com/siteverify",
    CaptchaType.CF_TURNSTILE: "https://challenges.cloudflare.com/turnstile/v0/siteverify",
}
HCAPTCHA_WITHHELD_HOSTNAME = "not-provided"


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        token_repository: TokenRepository,
        password_hasher: PasswordHasherProtocol,
        setting_service: SettingService,
        plugin_registry: PluginRegistry,
        settings: Settings,
    ) -> None:
        self.session = session
        self.user_repository = user_repository
        self.token_repository = token_repository
        self.password_hasher = password_hasher
        self.setting_service = setting_service
        self.plugin_registry = plugin_registry
        self.settings = settings

    async def authenticate_user(self, email: str, password: str) -> tuple[models.User | bool, int]:
        user = await self.user_repository.get_one_or_none(email=email)
        if not user:
            return False, 404
        if not self.password_hasher.verify_password(password, user.hashed_password):
            return False, 401
        return user, 200

    async def find_by_token(self, token: str) -> tuple[models.User, models.Token] | None:
        result = await self.token_repository.get_one_or_none(id=token, load=[joinedload(models.Token.user)])
        if not result or not result.user:
            return None
        return result.user, result

    async def find_user_and_check_permissions(
        self,
        header_token: str | None,
        security_scopes: SecurityScopes,
        request: Request | None = None,
    ) -> tuple[models.User, models.Token]:
        authenticate_value = self.get_authenticate_value(security_scopes)
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

    @staticmethod
    def get_authenticate_value(security_scopes: SecurityScopes) -> str:
        return f'Bearer scope="{security_scopes.scope_str}"' if security_scopes.scopes else "Bearer"

    async def require_scopes(
        self, user: models.User, token: models.Token, scopes: list[AuthScopes], request: Request | None = None
    ) -> None:
        security_scopes = SecurityScopes(cast(list[str], scopes))
        await self.check_permissions(user, token, security_scopes, request, self.get_authenticate_value(security_scopes))

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

    async def fetch_captcha_result(
        self, captcha_type: str, code: str, secret: str, client_ip: str | None = None
    ) -> dict[str, Any]:
        data = {"response": code, "secret": secret}
        if client_ip:
            data["remoteip"] = client_ip
        try:
            response, body = await utils.common.send_request(
                "POST",
                CAPTCHA_URLS[captcha_type],
                data=data,
                return_json=False,
                timeout=ClientTimeout(total=CAPTCHA_TIMEOUT),
            )
            response.raise_for_status()
            result = json.loads(body)
            if not isinstance(result, dict) or not isinstance(result.get("success"), bool):
                raise ValueError("unexpected response")
        except Exception as e:
            logger.error(f"Captcha provider {captcha_type} is unavailable: {get_exception_message(e)}")
            raise HTTPException(503, "Captcha verification is unavailable. Please try again later.") from None
        return result

    def get_captcha_rejection(self, captcha_type: str, result: dict[str, Any], action: CaptchaAction | None) -> str | None:
        if not result["success"]:
            return f"provider returned {result.get('error-codes')}"
        hostname = result.get("hostname")
        expected_hostname = urlsplit(f"//{self.settings.ADMIN_HOST}").hostname
        is_withheld = captcha_type == CaptchaType.HCAPTCHA and hostname == HCAPTCHA_WITHHELD_HOSTNAME
        if not hostname or (hostname != expected_hostname and not is_withheld):
            return f"solved on {hostname!r}, the admin panel is on {expected_hostname!r}"
        if captcha_type == CaptchaType.CF_TURNSTILE and action is not None and result.get("action") != action:
            return f"solved for action {result.get('action')!r} instead of {action.value!r}"
        return None

    async def captcha_flow(self, code: str | None, action: CaptchaAction | None = None, client_ip: str | None = None) -> None:
        policies = await self.setting_service.get_setting(Policy)
        if policies.captcha_type == CaptchaType.NONE:
            return
        rejection: str | None = "no code"
        if code:
            result = await self.fetch_captcha_result(policies.captcha_type, code, policies.captcha_secretkey, client_ip)
            rejection = self.get_captcha_rejection(policies.captcha_type, result, action)
        if rejection is not None:
            logger.warning(f"Captcha rejected: {rejection}")
            await self.plugin_registry.run_hook("captcha_failed")
            raise HTTPException(401, {"message": "Unauthorized", "status": 403})
        await self.plugin_registry.run_hook("captcha_passed")
