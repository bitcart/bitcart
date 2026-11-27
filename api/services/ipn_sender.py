import traceback
from typing import Any

from api.logging import get_logger
from api.services.outbound import OutboundService
from api.services.plugin_registry import PluginRegistry

logger = get_logger(__name__)

# TODO: IPN v2


class IPNSender:
    def __init__(self, plugin_registry: PluginRegistry, outbound: OutboundService) -> None:
        self.plugin_registry = plugin_registry
        self.outbound = outbound

    async def send_invoice_ipn(self, obj: Any, status: str) -> None:  # pragma: no cover
        if obj.notification_url:
            data = await self.plugin_registry.apply_filters("ipn_data", {"id": obj.id, "status": status}, obj, status)
            base_log_message = f"Sending IPN with data {data} to {obj.notification_url}"
            try:
                await self.plugin_registry.run_hook("send_ipn", obj, status, data)
                async with (
                    self.outbound.session() as session,
                    session.post(obj.notification_url, json=data, allow_redirects=False) as response,
                ):
                    status_code = response.status
                if 300 <= status_code < 400:
                    logger.info(f"{base_log_message}: error, redirects are not followed (HTTP {status_code})")
                else:
                    logger.info(f"{base_log_message}: success")
            except Exception:
                logger.info(f"{base_log_message}: error\n{traceback.format_exc()}")
