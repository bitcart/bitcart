from api.schemas.base import MetadataInput, MetadataOutput, TimestampedSchema


class CreateTemplate(MetadataInput):
    name: str
    text: str


class UpdateTemplate(CreateTemplate):
    pass


class DisplayTemplate(MetadataOutput, CreateTemplate, TimestampedSchema):
    id: str
    user_id: str
