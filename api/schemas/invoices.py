from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, EmailStr, field_validator, model_validator

from api.ext.moneyformat import currency_table
from api.schemas.base import DecimalAsString, MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.types import Money


# TODO: type all fields, plugin-extended ones will be allowed by allow
class PaymentData(Schema):
    created: datetime
    recommended_fee: DecimalAsString

    model_config = ConfigDict(extra="allow")


class BaseInvoice(MetadataInput):
    order_id: str = ""
    notification_url: str | None = ""
    redirect_url: str | None = ""
    buyer_email: EmailStr | Literal[""] | None = ""
    shipping_address: str = ""
    notes: str = ""


class CreateInvoice(BaseInvoice):
    price: Decimal
    store_id: str
    currency: str = ""
    promocode: str | None = ""
    products: list[str] | dict[str, int] = {}
    expiration: int | None = None
    payment_methods: list[str] | None = None

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


class MarkCompleteOptions(Schema):
    payment_method_id: str | None = None
    sent_amount: Decimal | None = None
    tx_hashes: list[str] | None = None
    tx_amounts: dict[str, Decimal] | None = None


class UpdateInvoice(BaseInvoice):
    pass


class DisplayInvoice(MetadataOutput, BaseInvoice, TimestampedSchema):
    id: str
    user_id: str
    store_id: str | None
    time_left: int
    expiration_seconds: int
    product_names: dict[str, Any]
    product_quantities: dict[str, int]
    payments: list[PaymentData]
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
    promocode: str | None
    products: list[str]
    sent_amount: Money
    sent_price: DecimalAsString
    sent_price_str: str
    effective_price: Money
    expiration: int
    payment_methods: list[str]

    @model_validator(mode="before")
    @classmethod
    def set_price(cls, values: dict[str, Any]) -> dict[str, Any]:
        from api.services.crud import invoices

        values["products"] = [v.id for v in values["products"]]
        sent_amount = values["sent_amount"]
        payment_id = values["payment_id"]
        values["effective_price"] = invoices.InvoiceService.find_effective_price(
            values["currency"], values["price"], values["payments"], payment_id
        )
        values["price"] = currency_table.format_decimal(values["currency"], values["price"])
        values.update(invoices.InvoiceService.find_sent_price(values["currency"], sent_amount, values["payments"], payment_id))
        values["sent_amount"] = currency_table.format_decimal(
            "",
            sent_amount,
            divisibility=invoices.InvoiceService.find_sent_amount_divisibility(values["id"], values["payments"], payment_id),
        )
        values["payments"] = [
            method.to_payment_dict(
                values["currency"],
                index,
                due=invoices.InvoiceService.find_due(method, values["status"], payment_id, sent_amount),
            )
            for index, method in invoices.InvoiceService.get_methods_inds(values["payments"])
        ]
        return values
