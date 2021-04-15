import re

from aiohttp import ClientSession

from api import settings
from api.constants import VERSION
from api.logger import get_logger

logger = get_logger(__name__)

RELEASE_REGEX = r"^([0-9]+(.[0-9]+)*(-[0-9]+)?)$"
REDIS_KEY = "bitcartcc_update_ext"


async def get_update_data():
    try:
        async with ClientSession() as session:
            async with session.get(settings.UPDATE_URL) as resp:
                data = await resp.json()
                tag = data["tag_name"]
                if re.match(RELEASE_REGEX, tag):
                    return tag
    except Exception as e:
        logger.error(f"Update check failed: {e}")


async def refresh():
    from api import schemes, utils

    async with utils.redis.wait_for_redis():
        if settings.UPDATE_URL and (await utils.policies.get_setting(schemes.Policy)).check_updates:
            logger.info("Checking for updates...")
            latest_tag = await get_update_data()
            if latest_tag and VERSION != latest_tag:
                logger.info(f"New update available: {latest_tag}")
                await settings.redis_pool.hset(REDIS_KEY, "new_update_tag", latest_tag)
            else:
                logger.info("No updates found")
                await settings.redis_pool.hdel(REDIS_KEY, "new_update_tag")  # clean after previous checks
