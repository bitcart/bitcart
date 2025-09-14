from api.schemas.base import MetadataInput, MetadataOutput, TimestampedSchema


class CreateFile(MetadataInput):
    pass


class UpdateFile(CreateFile):
    pass


class DisplayFile(MetadataOutput, CreateFile, TimestampedSchema):
    id: str
    user_id: str
    filename: str
