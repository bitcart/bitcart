from api.schemas.base import MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.templates import TemplateFormat


class CreateTemplate(MetadataInput):
    name: str
    text: str
    format: TemplateFormat = TemplateFormat.TEXT


class UpdateTemplate(CreateTemplate):
    pass


class DisplayTemplate(MetadataOutput, CreateTemplate, TimestampedSchema):
    id: str
    user_id: str


class TemplateTestRequest(Schema):
    name: str | None = None
    owner_id: str | None = None


class TemplateTestResult(Schema):
    ok: bool
    text: str = ""
    is_html: bool = False
    line: int | None = None
    source_line: str | None = None
    error: str | None = None
