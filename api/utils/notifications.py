import traceback
from decimal import Decimal

import notifiers
from aiohttp import ClientSession

from api import models, utils
from api.logger import get_logger
from api.plugins import apply_filters, run_hook

logger = get_logger(__name__)


async def send_ipn(obj, status):  # pragma: no cover
    if obj.notification_url:
        data = await apply_filters("ipn_data", {"id": obj.id, "status": status}, obj, status)
        base_log_message = f"Sending IPN with data {data} to {obj.notification_url}"
        try:
            await run_hook("send_ipn", obj, status, data)
            async with ClientSession() as session:
                await session.post(obj.notification_url, json=data)
            logger.info(f"{base_log_message}: success")
        except Exception:
            logger.info(f"{base_log_message}: error\n{traceback.format_exc()}")


# Apply common type conversions which aren't user errors
def validate_data(provider, data):
    for error in provider.validator.iter_errors(data):
        if "type" in error.schema and len(error.absolute_path) == 1:
            field_type = error.schema["type"]
            field_name = error.absolute_path[0]
            try:
                if field_type == "integer":
                    data[field_name] = int(data[field_name])
                elif field_type == "number":
                    data[field_name] = Decimal(data[field_name])
                elif field_type == "boolean":
                    data[field_name] = utils.common.str_to_bool(data[field_name])
            except Exception:
                pass
    return data


async def notify(store, text):  # pragma: no cover
    notification_providers = await utils.database.get_objects(models.Notification, store.notifications)
    for db_provider in notification_providers:
        provider = notifiers.get_notifier(db_provider.provider)
        data = validate_data(provider, db_provider.data)
        await run_hook("notify", db_provider, text, data)
        provider.notify(message=text, **data)
