from datetime import datetime

from pydantic import Field

from api.schemas.base import MetadataInput, MetadataOutput, TimestampedSchema


class CreateDiscount(MetadataInput):
    name: str
    percent: int = Field(ge=0, le=100)
    end_date: datetime
    description: str = ""
    promocode: str = ""
    currencies: str = ""


class UpdateDiscount(CreateDiscount):
    pass


class DisplayDiscount(MetadataOutput, CreateDiscount, TimestampedSchema):
    id: str
    user_id: str
