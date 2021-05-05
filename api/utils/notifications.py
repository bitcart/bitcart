import notifiers
from aiohttp import ClientSession

from api import models


async def send_ipn(obj, status):  # pragma: no cover
    if obj.notification_url:
        data = {"id": obj.id, "status": status}
        try:
            async with ClientSession() as session:
                await session.post(obj.notification_url, json=data)
        except Exception:
            pass


async def notify(store, text):  # pragma: no cover
    # TODO: N queries
    notification_providers = [await models.Notification.get(notification_id) for notification_id in store.notifications]
    for provider in notification_providers:
        notifiers.notify(provider.provider, message=text, **provider.data)
