from typing import Any, cast

from pydantic import field_validator, model_validator

from api import utils
from api.ext.moneyformat import currency_table
from api.schemas.base import DecimalAsFloat, MetadataInput, MetadataOutput, TimestampedSchema
from api.schemas.discounts import DisplayDiscount
from api.types import Money


class BaseProduct(MetadataInput):
    name: str
    quantity: int
    download_url: str = ""
    description: str = ""
    category: str = ""
    image: str = ""
    discounts: list[str] = []
    templates: dict[str, str] = {}


class CreateProduct(BaseProduct):
    store_id: str
    price: DecimalAsFloat


class UpdateProduct(CreateProduct):
    status: str


OptionalProductSchema = utils.common.to_optional(UpdateProduct)


class DisplayProduct(MetadataOutput, BaseProduct, TimestampedSchema):
    id: str
    status: str
    user_id: str
    store_id: str | None  # TODO: reconsider cascade handling!
    price: Money

    @model_validator(mode="before")
    @classmethod
    def set_price(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "price" in values:
            values["price"] = currency_table.format_decimal(cast(str, values.get("currency")), values["price"])
        return values

    @field_validator("discounts", mode="before")
    @classmethod
    def validate_discounts(cls, v: list[DisplayDiscount]) -> list[str]:
        return [d.id for d in v]
