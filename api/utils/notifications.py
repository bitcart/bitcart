import traceback

import notifiers
from aiohttp import ClientSession

from api import models, utils
from api.logger import get_logger

logger = get_logger(__name__)


async def send_ipn(obj, status):  # pragma: no cover
    if obj.notification_url:
        data = {"id": obj.id, "status": status}
        base_log_message = f"Sending IPN with data {data} to {obj.notification_url}"
        try:
            async with ClientSession() as session:
                await session.post(obj.notification_url, json=data)
            logger.info(f"{base_log_message}: success")
        except Exception:
            logger.info(f"{base_log_message}: error\n{traceback.format_exc()}")


async def notify(store, text):  # pragma: no cover
    notification_providers = await utils.database.get_objects(models.Notification, store.notifications)
    for provider in notification_providers:
        notifiers.notify(provider.provider, message=text, **provider.data)
