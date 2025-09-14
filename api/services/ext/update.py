import asyncio
import os
import re
from collections.abc import Awaitable
from typing import Any, cast

from aiohttp import ClientSession
from dishka import AsyncContainer, Scope
from sqlalchemy import distinct, func, select

from api import models, utils
from api.constants import VERSION
from api.db import AsyncSession
from api.logging import get_exception_message, get_logger
from api.redis import Redis
from api.schemas.policies import Policy
from api.services.coins import CoinService
from api.services.ext.tor import TorService
from api.services.plugin_manager import PluginManager
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.utils.common import run_repeated

logger = get_logger(__name__)

RELEASE_REGEX = r"^([0-9]+(.[0-9]+)*(-[0-9]+)?)$"
REDIS_KEY = "bitcart_update_ext"


class UpdateCheckService:
    def __init__(
        self,
        coin_service: CoinService,
        settings: Settings,
        redis_pool: Redis,
        tor_service: TorService,
        container: AsyncContainer,
        plugin_manager: PluginManager,
        plugin_registry: PluginRegistry,
    ) -> None:
        self.coin_service = coin_service
        self.container = container
        self.redis_pool = redis_pool
        self.tor_service = tor_service
        self.settings = settings
        self.plugin_manager = plugin_manager
        self.plugin_registry = plugin_registry

    async def collect_stats(self, session: AsyncSession) -> dict[str, Any]:
        total_invoices = await utils.database.get_scalar(session, select(models.Invoice), func.count, models.Invoice.id)
        complete_invoices = await utils.database.get_scalar(
            session, select(models.Invoice).where(models.Invoice.status == "complete"), func.count, models.Invoice.id
        )
        total_users = await utils.database.get_scalar(session, select(models.User), func.count, models.User.id)
        total_price_results = (
            await session.execute(
                select(models.Invoice.currency, func.sum(models.Invoice.price))
                .where(models.Invoice.status == "complete")
                .where(func.cardinality(models.Invoice.tx_hashes) > 0)
                .group_by(models.Invoice.currency)
            )
        ).all()
        total_price = {currency: str(price) for currency, price in total_price_results}
        subquery = (
            select(models.PaymentMethod)
            .where(models.PaymentMethod.invoice_id == models.Invoice.id)
            .with_only_columns(func.count(distinct(models.PaymentMethod.id)).label("count"))
            .group_by(models.Invoice.id)
            .alias("table")
        )
        average_number_of_methods_per_invoice = int(
            (await session.execute(select(func.avg(subquery.c.count)).select_from(subquery))).scalar() or 0
        )
        average_creation_time = await utils.database.get_scalar(
            session, select(models.Invoice), func.avg, models.Invoice.creation_time, use_distinct=False
        )
        average_paid_time = (
            (
                await session.execute(
                    select(func.avg(func.extract("epoch", (models.Invoice.paid_date - models.Invoice.created))))
                )
            ).scalar()
            or 0
        ) / 60
        plugins = [
            {"name": plugin["name"], "author": plugin["author"], "version": plugin["version"]}
            for plugin in self.plugin_manager.get_plugins()
        ]
        return {
            "version": VERSION,
            "hostname": os.getenv("BITCART_HOST", ""),
            "tor_services": await self.tor_service.get_data("anonymous_services_dict", {}, json_decode=True),
            "plugins": plugins,
            "total_invoices": total_invoices,
            "complete_invoices": complete_invoices,
            "total_users": total_users,
            "total_price": total_price,
            "average_invoice_creation_time": str(average_creation_time),
            "number_of_methods": average_number_of_methods_per_invoice,
            "currencies": list(self.coin_service.cryptos.keys()),
            "average_paid_time": str(average_paid_time),
        }

    async def get_update_data(self) -> str | None:
        try:
            update_url = cast(str, self.settings.UPDATE_URL)
            async with ClientSession() as session:
                if update_url.startswith("https://api.github.com"):
                    async with session.get(update_url) as resp:
                        data = await resp.json()
                else:
                    async with self.container(scope=Scope.REQUEST) as request_container:
                        db_session = await request_container.get(AsyncSession)
                        async with session.post(update_url, json=await self.collect_stats(db_session)) as resp:
                            data = await resp.json()
                tag = data["tag_name"]
                if re.match(RELEASE_REGEX, tag):
                    return tag
                return None

        except Exception as e:
            logger.error(f"Update check failed: {get_exception_message(e)}")
            return None

    async def refresh(self) -> None:
        if self.settings.UPDATE_URL:
            async with self.container(scope=Scope.REQUEST) as container:
                setting_service = await container.get(SettingService)
                check_updates = (await setting_service.get_setting(Policy)).check_updates
            if not check_updates:
                return
            logger.info("Checking for updates...")
            latest_tag = await self.plugin_registry.apply_filters("update_latest_tag", await self.get_update_data())
            if latest_tag and utils.common.versiontuple(latest_tag) > utils.common.versiontuple(VERSION):
                logger.info(f"New update available: {latest_tag}")
                await cast(Awaitable[int], self.redis_pool.hset(REDIS_KEY, "new_update_tag", latest_tag))
            else:
                logger.info("No updates found")
                await cast(Awaitable[int], self.redis_pool.hdel(REDIS_KEY, "new_update_tag"))  # clean after previous checks

    async def start(self) -> None:
        asyncio.create_task(self.refresh())
        asyncio.create_task(run_repeated(self.refresh, 60 * 60 * 24))

    async def get_latest_fetched_update(self) -> dict[str, Any]:
        new_update_tag = await cast(Awaitable[str | None], self.redis_pool.hget(REDIS_KEY, "new_update_tag"))
        return {"update_available": bool(new_update_tag), "tag": new_update_tag}
