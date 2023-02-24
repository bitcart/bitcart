import os
import re

from aiohttp import ClientSession
from sqlalchemy import distinct, select

from api import db, models, settings, utils
from api.constants import VERSION
from api.ext.plugins import get_plugins
from api.logger import get_exception_message, get_logger
from api.plugins import apply_filters

logger = get_logger(__name__)

RELEASE_REGEX = r"^([0-9]+(.[0-9]+)*(-[0-9]+)?)$"
REDIS_KEY = "bitcartcc_update_ext"


async def collect_stats():
    total_invoices = await utils.database.get_scalar(models.Invoice.query, db.db.func.count, models.Invoice.id)
    complete_invoices = await utils.database.get_scalar(
        models.Invoice.query.where(models.Invoice.status == "complete"), db.db.func.count, models.Invoice.id
    )
    total_users = await utils.database.get_scalar(models.User.query, db.db.func.count, models.User.id)
    total_price = (
        await select([models.Invoice.currency, db.db.func.sum(models.Invoice.price)])
        .where(models.Invoice.status == "complete")
        .where(db.db.func.cardinality(models.Invoice.tx_hashes) > 0)
        .group_by(models.Invoice.currency)
        .gino.all()
    )
    total_price = {currency: str(price) for currency, price in total_price}
    subquery = (
        models.PaymentMethod.query.where(models.PaymentMethod.invoice_id == models.Invoice.id)
        .with_only_columns([db.db.func.count(distinct(models.PaymentMethod.id)).label("count")])
        .group_by(models.Invoice.id)
        .alias("table")
    )
    average_number_of_methods_per_invoice = int(
        await select([db.db.func.avg(subquery.c.count)]).select_from(subquery).gino.scalar() or 0
    )
    average_creation_time = await utils.database.get_scalar(
        models.Invoice.query, db.db.func.avg, models.Invoice.creation_time, use_distinct=False
    )
    plugins = [{"name": plugin["name"], "author": plugin["author"], "version": plugin["version"]} for plugin in get_plugins()]
    return {
        "version": VERSION,
        "hostname": os.getenv("BITCART_HOST", ""),
        "plugins": plugins,
        "total_invoices": total_invoices,
        "complete_invoices": complete_invoices,
        "total_users": total_users,
        "total_price": total_price,
        "average_invoice_creation_time": str(average_creation_time),
        "number_of_methods": average_number_of_methods_per_invoice,
        "currencies": list(settings.settings.cryptos.keys()),
    }


async def get_update_data():
    try:
        async with ClientSession() as session:
            if settings.settings.update_url.startswith("https://api.github.com"):
                resp = await session.get(settings.settings.update_url)
            else:
                resp = await session.post(settings.settings.update_url, json=await collect_stats())
            data = await resp.json()
            resp.release()
            tag = data["tag_name"]
            if re.match(RELEASE_REGEX, tag):
                return tag

    except Exception as e:
        logger.error(f"Update check failed: {get_exception_message(e)}")


async def refresh():
    from api import schemes, utils

    async with utils.redis.wait_for_redis():
        if settings.settings.update_url and (await utils.policies.get_setting(schemes.Policy)).check_updates:
            logger.info("Checking for updates...")
            latest_tag = await apply_filters("update_latest_tag", await get_update_data())
            if latest_tag and utils.common.versiontuple(latest_tag) > utils.common.versiontuple(VERSION):
                logger.info(f"New update available: {latest_tag}")
                await settings.settings.redis_pool.hset(REDIS_KEY, "new_update_tag", latest_tag)
            else:
                logger.info("No updates found")
                await settings.settings.redis_pool.hdel(REDIS_KEY, "new_update_tag")  # clean after previous checks
