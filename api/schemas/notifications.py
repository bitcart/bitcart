from typing import Any

from api.schemas.base import MetadataInput, MetadataOutput, TimestampedSchema


class CreateNotification(MetadataInput):
    name: str
    provider: str
    data: dict[str, Any]


class UpdateNotification(CreateNotification):
    pass


class DisplayNotification(MetadataOutput, CreateNotification, TimestampedSchema):
    id: str
    user_id: str
    error: bool = False
