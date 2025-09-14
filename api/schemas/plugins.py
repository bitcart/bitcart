from api.schemas.base import Schema


class UninstallPluginData(Schema):
    author: str
    name: str


class AddLicenseRequest(Schema):
    license_key: str
