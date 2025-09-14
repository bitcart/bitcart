import contextlib
from typing import Any, cast

import apprise
from dishka import AsyncContainer, Scope

from api import models, utils
from api.ext.notifiers import all_notifers, get_notifier, get_params
from api.logging import get_logger
from api.services.crud.stores import StoreService

logger = get_logger(__name__)


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

    async def notify(self, store: models.Store, text: str) -> bool:  # pragma: no cover
        appr = apprise.Apprise()
        async with self.container(scope=Scope.REQUEST) as container:
            store_service = await container.get(StoreService)
            store = await store_service.get(store.id)
        notification_providers = store.notifications
        for db_provider in notification_providers:
            provider_schema = get_notifier(db_provider.provider)
            data = self.validate_data(cast(dict[str, Any], provider_schema), db_provider.data)
            try:
                provider = apprise.Apprise.instantiate(data, suppress_exceptions=False)
            except Exception as e:
                logger.error(f"Failed to instantiate provider {db_provider.provider}: {e}")
                return False
            appr.add(cast(apprise.NotifyBase, provider))
        with apprise.LogCapture(level=apprise.logging.INFO) as output:
            if not await appr.async_notify(text):
                error_message = output.getvalue().strip()
                if "There are no service(s) to notify" not in error_message:
                    logger.error(f"Failed to send some notifications of store {store.id}:\n{error_message}")
                return False
        return True
