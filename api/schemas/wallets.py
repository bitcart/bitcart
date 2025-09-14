from typing import Any, cast

from pydantic import Field, field_validator, model_validator

from api.ext.moneyformat import currency_table
from api.schemas.base import MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.schemas.users import InfoUser
from api.types import Money


class CreateWallet(MetadataInput):
    name: str
    xpub: str
    currency: str = Field("btc", validate_default=True)
    lightning_enabled: bool = False
    label: str = ""
    hint: str = ""
    contract: str = ""
    additional_xpub_data: dict[str, Any] = {}

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.lower()


class CreateWalletData(Schema):
    currency: str
    hot_wallet: bool


class UpdateWallet(CreateWallet):
    pass


class InfoWallet(MetadataOutput, CreateWallet):
    id: str
    user_id: str


class DisplayWallet(InfoWallet, TimestampedSchema):
    user: "InfoUser"
    balance: Money
    error: bool = False

    @model_validator(mode="before")
    @classmethod
    def set_balance(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "balance" in values:
            values["balance"] = currency_table.format_decimal(
                cast(str, values.get("currency")), values["balance"], divisibility=values.get("divisibility")
            )
        return values
