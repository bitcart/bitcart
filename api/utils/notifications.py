import traceback

import apprise
from aiohttp import ClientSession

from api import models, utils
from api.ext.notifiers import get_notifier
from api.logger import get_logger
from api.plugins import apply_filters, run_hook

logger = get_logger(__name__)


async def send_ipn(obj, status):  # pragma: no cover
    if obj.notification_url:
        data = await apply_filters("ipn_data", {"id": obj.id, "status": status}, obj, status)
        base_log_message = f"Sending IPN with data {data} to {obj.notification_url}"
        try:
            await run_hook("send_ipn", obj, status, data)
            async with ClientSession() as session, session.post(obj.notification_url, json=data) as resp:  # noqa: F841
                pass
            logger.info(f"{base_log_message}: success")
        except Exception:
            logger.info(f"{base_log_message}: error\n{traceback.format_exc()}")


# Apply common type conversions which aren't user errors
def validate_data(provider, data):  # pragma: no cover
    for json_part in ("args", "tokens"):
        for k, v in provider["details"][json_part].items():
            if "type" in v and k in data:
                field_type = v["type"]
                try:
                    if field_type == "int":
                        data[k] = int(data[k])
                    elif field_type == "float":
                        data[k] = float(data[k])
                    elif field_type == "bool":
                        data[k] = utils.common.str_to_bool(data[k])
                except Exception:
                    pass
    data["schema"] = provider["details"]["tokens"]["schema"]["values"][0]
    return data


async def notify(store, text):  # pragma: no cover
    appr = apprise.Apprise()
    notification_providers = await utils.database.get_objects(models.Notification, store.notifications)
    for db_provider in notification_providers:
        provider_schema = get_notifier(db_provider.provider)
        data = validate_data(provider_schema, db_provider.data)
        try:
            provider = apprise.Apprise.instantiate(data, suppress_exceptions=False)
        except Exception as e:
            logger.error(f"Failed to instantiate provider {db_provider.provider}: {e}")
            return False
        appr.add(provider)
    with apprise.LogCapture(level=apprise.logging.INFO) as output:
        if not await appr.async_notify(text):
            logger.error(f"Failed to send some notifications of store {store.id}:\n{output.getvalue().strip()}")
            return False
    return True
