import re

from aiohttp import ClientSession

from api import settings
from api.version import VERSION

RELEASE_REGEX = r"^([0-9]+(.[0-9]+)*(-[0-9]+)?)$"


async def get_update_data():
    try:
        async with ClientSession() as session:
            async with session.get(settings.UPDATE_URL) as resp:  # pragma: no cover
                data = await resp.json()
                tag = data["tag_name"]
                if re.match(RELEASE_REGEX, tag):
                    return tag
    except Exception:
        pass


class UpdateExtension:
    new_update_tag = None


async def refresh():
    from api import schemes, utils

    if (await utils.get_setting(schemes.Policy)).check_updates:
        latest_tag = await get_update_data()
        if VERSION != latest_tag:
            UpdateExtension.new_update_tag = latest_tag
