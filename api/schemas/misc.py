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


class HostAgentState(Schema):
    configured: bool = False
    available: bool = False
    checked_at: int | None = None
    unreachable_since: int | None = None
    error: str | None = None
    capabilities: dict[str, Any] | None = None


class HostAgentJob(Schema):
    job_id: str
    command: str
    state: str = "running"


class HostAgentOverview(Schema):
    state: HostAgentState
    jobs: dict[str, HostAgentJob]


class HostAgentJobStatus(Schema):
    id: str
    command: str
    state: str
    reason: str | None = None
    created: int | None = None
    started: int | None = None
    finished: int | None = None
    exit_code: int | None = None
    result: dict[str, Any] | None = None
    log: str
    log_complete: bool


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
