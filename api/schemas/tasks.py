from typing import Any

from api.schemas.base import Schema
from api.schemas.policies import BackupsPolicy


class SendMailMessage(Schema):
    to: str
    subject: str
    text: str


class RatesActionMessage(Schema):
    func: str
    args: tuple[Any, ...]
    task_id: str


class SendVerificationEmailMessage(Schema):
    user_id: str


class SyncWalletMessage(Schema):
    wallet_id: str


class SendNotificationMessage(Schema):
    store_id: str
    text: str


class ProcessNewBackupPolicyMessage(Schema):
    old_policy: BackupsPolicy
    new_policy: BackupsPolicy


class DeployTaskMessage(Schema):
    task_id: str


class LicenseChangedMessage(Schema):
    license_key: str | None
    license_info: dict[str, Any] | None


class PluginTaskMessage(Schema):
    event: str
    data: Schema
    for_worker: bool = True
