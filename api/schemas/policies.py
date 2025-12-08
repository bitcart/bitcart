from typing import Any

from fastapi import HTTPException
from pydantic import field_validator

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS
from api.schemas.base import Schema
from api.schemas.misc import CaptchaType, EmailSettings


class Policy(Schema):
    _SECRET_FIELDS = {"captcha_secretkey", "email_settings"}

    allow_powered_by_bitcart: bool = False
    disable_registration: bool = False
    require_verified_email: bool = False
    allow_file_uploads: bool = True
    discourage_index: bool = False
    check_updates: bool = True
    staging_updates: bool = False
    allow_anonymous_configurator: bool = True
    captcha_sitekey: str = ""
    captcha_secretkey: str = ""
    admin_theme_url: str = ""
    captcha_type: str = CaptchaType.NONE
    use_html_templates: bool = False
    global_templates: dict[str, str] = {}
    explorer_urls: dict[str, str] = {}
    rpc_urls: dict[str, str] = {}
    email_settings: EmailSettings = EmailSettings()
    health_check_store_id: str = ""
    allow_eth_plugin_info: bool = True

    @field_validator("captcha_type")
    @classmethod
    def validate_captcha_type(cls, v: str) -> str:
        if v not in CaptchaType:
            raise HTTPException(422, f"Invalid captcha_type. Expected either of {', '.join(CaptchaType)}.")
        return v


class GlobalStorePolicy(Schema):
    pos_id: str = ""


class BackupsPolicy(Schema):
    provider: str = "local"
    scheduled: bool = False
    frequency: str = "weekly"
    environment_variables: dict[str, str] = {}

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        from api import utils

        return utils.common.validate_list(v, BACKUP_PROVIDERS, "Backup provider")

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        from api import utils

        return utils.common.validate_list(v, BACKUP_FREQUENCIES, "Backup frequency")


class PluginsState(Schema):
    license_keys: dict[str, dict[str, Any]] = {}
