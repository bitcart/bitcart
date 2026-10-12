from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pydantic import ValidatorFunctionWrapHandler, field_validator, model_validator

from api.ext.moneyformat import currency_table, format_raw
from api.schemas.base import MetadataInput, MetadataOutput, TimestampedSchema
from api.types import Money


class BasePayout(MetadataInput):
    destination: str
    currency: str = ""
    notification_url: str = ""

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()


class CreatePayout(BasePayout):
    amount: Decimal
    store_id: str
    wallet_id: str
    max_fee: Decimal | None = None

    @field_validator("max_fee", mode="wrap")
    @classmethod
    def set_max_fee(cls, v: Any, handler: ValidatorFunctionWrapHandler) -> Decimal | None:
        return handler(v or None) or None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0 and v != -1:
            raise HTTPException(422, "Amount must be >= 0. Use -1 to send full balance.")
        return v


class UpdatePayout(CreatePayout):  # TODO: re-check
    pass


class DisplayPayout(MetadataOutput, BasePayout, TimestampedSchema):
    id: str
    user_id: str
    store_id: str | None
    wallet_id: str | None
    wallet_currency: str | None
    used_fee: Money | None
    tx_hash: str | None
    amount: Money
    max_fee: Money | None
    status: str

    @model_validator(mode="before")
    @classmethod
    def set_amount(cls, values: dict[str, Any]) -> dict[str, Any]:
        values["amount"] = currency_table.format_decimal(values["currency"], values["amount"])
        if values["max_fee"] is not None:
            values["max_fee"] = currency_table.format_decimal(values["currency"], values["max_fee"])
        if (used_fee := values["used_fee"]) is not None:
            wallet_currency = values["wallet_currency"]
            values["used_fee"] = (
                currency_table.format_decimal(wallet_currency, used_fee) if wallet_currency else format_raw(used_fee)
            )
        return values
