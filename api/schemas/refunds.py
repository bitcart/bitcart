from decimal import Decimal
from typing import Any

from pydantic import model_validator

from api.ext.moneyformat import currency_table
from api.schemas.base import MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.types import Money


class BaseRefund(MetadataInput):
    currency: str


class CreateRefund(BaseRefund):
    wallet_id: str
    invoice_id: str
    amount: Decimal


class UpdateRefund(CreateRefund):
    pass


class DisplayRefund(MetadataOutput, BaseRefund, TimestampedSchema):
    id: str
    user_id: str
    wallet_id: str | None
    invoice_id: str | None
    destination: str | None
    wallet_currency: str | None = None  # added at runtime
    payout_id: str | None
    payout_status: str | None = None
    tx_hash: str | None = None
    amount: Money

    @model_validator(mode="before")
    @classmethod
    def set_amount(cls, values: dict[str, Any]) -> dict[str, Any]:
        values["amount"] = currency_table.format_decimal(values["currency"], values["amount"])
        return values


class RefundData(Schema):
    amount: Decimal
    currency: str
    send_email: bool = True


class SubmitRefundData(Schema):
    destination: str
