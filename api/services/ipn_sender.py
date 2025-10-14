import traceback
from typing import Any

from api import utils
from api.logging import get_logger
from api.services.plugin_registry import PluginRegistry

logger = get_logger(__name__)

# TODO: IPN v2


class IPNSender:
    def __init__(self, plugin_registry: PluginRegistry) -> None:
        self.plugin_registry = plugin_registry

    async def send_invoice_ipn(self, obj: Any, status: str) -> None:  # pragma: no cover
        if obj.notification_url:
            data = await self.plugin_registry.apply_filters("ipn_data", {"id": obj.id, "status": status}, obj, status)
            base_log_message = f"Sending IPN with data {data} to {obj.notification_url}"
            try:
                await self.plugin_registry.run_hook("send_ipn", obj, status, data)
                # we don't need to enforce json responses here
                await utils.common.send_request("POST", obj.notification_url, json=data, return_json=False)
                logger.info(f"{base_log_message}: success")
            except Exception:
                logger.info(f"{base_log_message}: error\n{traceback.format_exc()}")
