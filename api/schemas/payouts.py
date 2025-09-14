from typing import Any

from pydantic import Field, field_validator, model_validator

from api.ext.moneyformat import currency_table
from api.schemas.base import DecimalAsFloat, MetadataInput, MetadataOutput, TimestampedSchema
from api.types import Money


class BasePayout(MetadataInput):
    destination: str
    currency: str = Field("", validate_default=True)
    notification_url: str = ""
    max_fee: DecimalAsFloat | None = Field(None, validate_default=True)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("max_fee", mode="before")  # TODO: why
    @classmethod
    def set_max_fee(cls, v: DecimalAsFloat | None) -> DecimalAsFloat | None:
        return v or None


class CreatePayout(BasePayout):
    amount: DecimalAsFloat
    store_id: str
    wallet_id: str


class UpdatePayout(CreatePayout):  # TODO: re-check
    pass


class DisplayPayout(MetadataOutput, BasePayout, TimestampedSchema):
    id: str
    user_id: str
    store_id: str | None
    wallet_id: str | None
    wallet_currency: str | None
    used_fee: DecimalAsFloat | None
    tx_hash: str | None
    amount: Money
    status: str

    @model_validator(mode="before")
    @classmethod
    def set_amount(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "amount" in values and "currency" in values:
            values["amount"] = currency_table.format_decimal(values["currency"], values["amount"])
        return values
