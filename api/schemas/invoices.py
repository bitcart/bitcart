from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator

from api.ext.moneyformat import currency_table
from api.schemas.base import DecimalAsFloat, MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.types import Money


# TODO: type all fields, plugin-extended ones will be allowed by allow
class PaymentData(Schema):
    created: datetime
    recommended_fee: DecimalAsFloat

    model_config = ConfigDict(extra="allow", from_attributes=True)


class BaseInvoice(MetadataInput):
    order_id: str = ""
    notification_url: str | None = ""
    redirect_url: str | None = ""
    buyer_email: EmailStr | Literal[""] | None = ""
    shipping_address: str = ""
    notes: str = ""


class CreateInvoice(BaseInvoice):
    price: DecimalAsFloat
    store_id: str
    currency: str = Field("", validate_default=True)
    promocode: str | None = ""
    products: list[str] | dict[str, int] = {}
    expiration: int | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()


class CustomerUpdateData(Schema):
    buyer_email: EmailStr | Literal[""] = ""
    shipping_address: str = ""
    notes: str = ""


class MethodUpdateData(Schema):
    id: str
    address: str


class UpdateInvoice(BaseInvoice):
    pass


class DisplayInvoice(MetadataOutput, BaseInvoice, TimestampedSchema):
    id: str
    user_id: str
    store_id: str | None
    time_left: int
    expiration_seconds: int
    product_names: dict[str, Any]
    payments: list[PaymentData] = []
    paid_date: datetime | None
    payment_id: str | None
    refund_id: str | None
    paid_currency: str | None
    discount: str | None
    price: Money

    status: str
    exception_status: str
    currency: str
    tx_hashes: list[str]
    promocode: str | None = ""  # TODO: fix this???
    products: list[str]
    sent_amount: DecimalAsFloat
    expiration: int

    @model_validator(mode="before")
    @classmethod
    def set_price(cls, values: dict[str, Any]) -> dict[str, Any]:
        from api.services.crud import invoices

        if "products" in values:
            values["product_names"] = {v.id: v.name for v in values["products"]}
            values["products"] = [v.id for v in values["products"]]
        if "price" in values and "currency" in values:
            values["price"] = currency_table.format_decimal(values["currency"], values["price"])
        if "sent_amount" in values:
            values["sent_amount"] = currency_table.format_decimal(
                "",
                values["sent_amount"],
                divisibility=invoices.InvoiceService.find_sent_amount_divisibility(
                    values["id"], values["payments"], values["payment_id"]
                ),
            )
        values["payments"] = [
            method.to_payment_dict(values["currency"], index)
            for index, method in invoices.InvoiceService.get_methods_inds(values["payments"])
        ]
        return values
