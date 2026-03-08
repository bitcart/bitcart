import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, cast

import apprise
from dishka import AsyncContainer, Scope

from api import models, utils
from api.ext.notifiers import all_notifers, get_notifier, get_params
from api.logging import get_logger
from api.services.crud.stores import StoreService

logger = get_logger(__name__)


# needed because we need to capture logs without sending them to logserver
@contextlib.contextmanager
def apprise_log_capture() -> Iterator[StringIO]:
    apprise_logger = logging.getLogger("apprise")
    old_disabled = apprise_logger.disabled
    old_propagate = apprise_logger.propagate
    old_level = apprise_logger.level
    apprise_logger.disabled = False
    apprise_logger.propagate = False
    apprise_logger.setLevel(logging.DEBUG)
    try:
        with apprise.LogCapture(level=logging.DEBUG) as output:
            yield output
    finally:
        apprise_logger.disabled = old_disabled
        apprise_logger.propagate = old_propagate
        apprise_logger.setLevel(old_level)


@dataclass
class NotifyResult:
    sent: int = 0
    failed: int = 0
    errors: list[Exception] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.sent > 0 and self.failed == 0

    @property
    def has_providers(self) -> bool:
        return (self.sent + self.failed) > 0


class NotificationManager:
    def __init__(self, container: AsyncContainer) -> None:
        self.container = container
        self.load_notification_providers()

    def load_notification_providers(self) -> None:
        self.notifiers = {}
        for notifier in all_notifers():
            self.notifiers[str(notifier["service_name"])] = {
                "properties": get_params(notifier),
                "required": get_params(notifier, need_required=True),
                "setup_url": notifier["setup_url"],
            }

    # Apply common type conversions which aren't user errors
    @staticmethod
    def validate_data(provider: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        for json_part in ("args", "tokens"):
            for k, v in provider["details"][json_part].items():
                if "type" in v and k in data:
                    field_type = v["type"]
                    with contextlib.suppress(Exception):
                        if field_type == "int":
                            data[k] = int(data[k])
                        elif field_type == "float":
                            data[k] = float(data[k])
                        elif field_type == "bool":
                            data[k] = utils.common.str_to_bool(data[k])
        data["schema"] = provider["details"]["tokens"]["schema"]["values"][0]
        return data

    async def notify(self, store: models.Store, text: str) -> NotifyResult:  # pragma: no cover
        result = NotifyResult()
        async with self.container(scope=Scope.REQUEST) as container:
            store_service = await container.get(StoreService)
            store = await store_service.get(store.id)
        for db_provider in store.notifications:
            provider_schema = get_notifier(db_provider.provider)
            data = self.validate_data(cast(dict[str, Any], provider_schema), db_provider.data)
            try:
                provider = apprise.Apprise.instantiate(data, suppress_exceptions=False)
            except Exception as e:
                logger.error(f"Failed to instantiate provider {db_provider.provider}: {e}")
                result.failed += 1
                result.errors.append(e)
                continue
            appr = apprise.Apprise()
            appr.add(cast(apprise.NotifyBase, provider))
            with apprise_log_capture() as output:
                if await appr.async_notify(text):
                    result.sent += 1
                else:
                    result.failed += 1
                    error_message = output.getvalue().strip()
                    result.errors.append(Exception(error_message))
                    logger.error(
                        f"Failed to send notification via {db_provider.provider} for store {store.id}:\n{error_message}"
                    )
        return result
