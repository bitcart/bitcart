import asyncio
import os
import re
from collections.abc import Awaitable
from typing import Any, cast

from aiohttp import ClientSession
from bitcart import COINS  # type: ignore[attr-defined]
from dishka import AsyncContainer, Scope
from sqlalchemy import func, select

from api import models, utils
from api.constants import VERSION
from api.db import AsyncSession
from api.logging import get_exception_message, get_logger
from api.redis import Redis
from api.schemas.policies import Policy
from api.services.coins import CoinService
from api.services.crud.repositories.invoices import InvoiceRepository
from api.services.crud.repositories.users import UserRepository
from api.services.ext.tor import TorService
from api.services.plugin_manager import PluginManager
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.utils.common import run_repeated

logger = get_logger(__name__)

RELEASE_REGEX = r"^([0-9]+(.[0-9]+)*(-[0-9]+)?)$"
REDIS_KEY = "bitcart_update_ext"
SELECTED_POLICY_KEYS = {
    "allow_powered_by_bitcart",
    "disable_registration",
    "require_verified_email",
    "discourage_index",
    "check_updates",
    "staging_updates",
    "allow_anonymous_configurator",
    "captcha_type",
    "use_html_templates",
    "allow_eth_plugin_info",
    "log_retention_days",
    "eth_plugin_active",
}


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

    async def collect_stats(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        invoice_repository: InvoiceRepository,
        setting_service: SettingService,
    ) -> dict[str, Any]:
        version = VERSION
        hostname = os.getenv("BITCART_HOST", "")
        tor_services = await self.tor_service.get_data("anonymous_services_dict", {}, json_decode=True)
        plugins = [
            {"name": plugin["name"], "author": plugin["author"], "version": plugin["version"]}
            for plugin in self.plugin_manager.get_plugins()
        ]
        total_users = await utils.database.get_scalar(session, select(models.User), func.count, models.User.id)
        total_wallets = await utils.database.get_scalar(session, select(models.Wallet), func.count, models.Wallet.id)
        total_stores = await utils.database.get_scalar(session, select(models.Store), func.count, models.Store.id)
        total_products = await utils.database.get_scalar(session, select(models.Product), func.count, models.Product.id)
        total_invoices = await utils.database.get_scalar(session, select(models.Invoice), func.count, models.Invoice.id)
        total_payouts = await utils.database.get_scalar(session, select(models.Payout), func.count, models.Payout.id)
        complete_invoices = await utils.database.get_scalar(
            session, select(models.Invoice).where(models.Invoice.status == "complete"), func.count, models.Invoice.id
        )
        complete_payouts = await utils.database.get_scalar(
            session, select(models.Payout).where(models.Payout.status == "complete"), func.count, models.Payout.id
        )
        eth_based_currencies = [
            key.lower() for key, coin in COINS.items() if coin.is_eth_based and coin.coin_name not in ("XMR",)
        ]
        total_price = await invoice_repository.get_complete_grouped_total_price()
        total_price_eth_based = await invoice_repository.get_complete_grouped_total_price(
            eth_based_currencies=eth_based_currencies, eth_based=True
        )
        invoice_status_counts = await invoice_repository.get_status_counts()
        average_invoice_creation_time = str(
            await utils.database.get_scalar(
                session, select(models.Invoice), func.avg, models.Invoice.creation_time, use_distinct=False
            )
        )
        number_of_methods = await invoice_repository.get_average_methods_number()
        currencies = list(self.coin_service.cryptos.keys())
        average_paid_time = str(await invoice_repository.get_average_paid_time())
        superuser = await user_repository.get_first_superuser()
        superuser_email = superuser.email if superuser else ""
        policy = await setting_service.get_setting(Policy)
        full_policy = await self.plugin_registry.apply_filters("get_global_policies", policy.model_dump())
        selected_policies = {k: full_policy[k] for k in SELECTED_POLICY_KEYS if k in full_policy}
        return {
            "version": version,
            "hostname": hostname,
            "tor_services": tor_services,
            "plugins": plugins,
            "total_users": total_users,
            "total_wallets": total_wallets,
            "total_stores": total_stores,
            "total_products": total_products,
            "total_invoices": total_invoices,
            "total_payouts": total_payouts,
            "complete_invoices": complete_invoices,
            "complete_payouts": complete_payouts,
            "total_price": total_price,
            "total_price_eth_based": total_price_eth_based,
            "invoice_status_counts": invoice_status_counts,
            "average_invoice_creation_time": average_invoice_creation_time,
            "number_of_methods": number_of_methods,
            "currencies": currencies,
            "average_paid_time": average_paid_time,
            "superuser_email": superuser_email,
            "selected_policies": selected_policies,
        }

    async def get_update_data(self) -> str | None:
        update_url = cast(str, self.settings.UPDATE_URL)
        async with ClientSession() as session:
            if update_url.startswith("https://api.github.com"):
                async with session.get(update_url) as resp:
                    data = await resp.json()
            else:
                async with self.container(scope=Scope.REQUEST) as request_container:
                    db_session = await request_container.get(AsyncSession)
                    user_repository = await request_container.get(UserRepository)
                    invoice_repository = await request_container.get(InvoiceRepository)
                    setting_service = await request_container.get(SettingService)
                    async with session.post(
                        update_url,
                        json=await self.collect_stats(db_session, user_repository, invoice_repository, setting_service),
                    ) as resp:
                        data = await resp.json()
            tag = data["tag_name"]
            if re.match(RELEASE_REGEX, tag):
                return tag
            return None

    async def refresh(self) -> None:
        if self.settings.UPDATE_URL:
            async with self.container(scope=Scope.REQUEST) as container:
                setting_service = await container.get(SettingService)
                check_updates = (await setting_service.get_setting(Policy)).check_updates
            if check_updates:
                logger.info("Checking for updates...")
            try:
                latest_tag = await self.plugin_registry.apply_filters("update_latest_tag", await self.get_update_data())
            except Exception as e:
                if check_updates:
                    logger.error(f"Update check failed: {get_exception_message(e)}")
                return
            if not check_updates:
                return
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
