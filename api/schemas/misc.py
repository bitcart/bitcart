import math
from typing import Any

from fastapi import HTTPException
from pydantic import Field, field_validator

from api.schemas.base import DecimalAsFloat, Schema
from api.types import Money, StrEnum


class SMTPAuthMode(StrEnum):
    NONE = "none"
    SSL_TLS = "ssl/tls"
    STARTTLS = "starttls"


class CaptchaType(StrEnum):
    NONE = "none"
    HCAPTCHA = "hcaptcha"
    CF_TURNSTILE = "cloudflare_turnstile"


class EmailSettings(Schema):  # all policies have DisplayModel
    address: str = ""
    host: str = ""
    port: int = 25
    user: str = ""
    password: str = ""
    auth_mode: str = SMTPAuthMode.STARTTLS

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, v: str) -> str:
        if v not in SMTPAuthMode:
            raise HTTPException(422, f"Invalid auth_mode. Expected either of {', '.join(SMTPAuthMode)}.")
        return v


class BatchAction(Schema):
    ids: list[str]
    command: str
    options: dict[str, Any] | list[dict[str, Any]] | None = {}


class BalanceResponse(Schema):
    confirmed: Money
    unconfirmed: Money
    unmatured: Money
    lightning: Money


class OpenChannelScheme(Schema):
    node_id: str
    amount: DecimalAsFloat


class CloseChannelScheme(Schema):
    channel_point: str
    force: bool = False


class LNPayScheme(Schema):
    invoice: str


class BackupState(Schema):
    last_run: int | None = None


class SSHSettings(Schema):
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    key_file: str = ""
    key_file_password: str = ""
    authorized_keys_file: str = ""
    bash_profile_script: str = ""


class RateResult(Schema):
    rate: DecimalAsFloat | None = Field(..., validate_default=True)
    message: str

    @field_validator("rate", mode="before")
    @classmethod
    def set_rate(cls, v: DecimalAsFloat) -> DecimalAsFloat | None:
        if math.isnan(v):
            return None
        return v


class RatesResponse(Schema):
    rates: list[RateResult]
