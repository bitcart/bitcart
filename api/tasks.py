import json

from dishka import FromDishka
from dishka.integrations.taskiq import inject
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListRedisScheduleSource, RedisAsyncResultBackend

from api import utils
from api.logging import get_exception_message, get_logger
from api.redis import Redis
from api.schemas.tasks import (
    DeployTaskMessage,
    LicenseChangedMessage,
    PluginTaskMessage,
    ProcessNewBackupPolicyMessage,
    RatesActionMessage,
    SendNotificationMessage,
    SendVerificationEmailMessage,
    SyncWalletMessage,
)
from api.services.backup_manager import BackupManager
from api.services.coins import CoinService
from api.services.crud.stores import StoreService
from api.services.crud.users import UserService
from api.services.crud.wallets import WalletService
from api.services.exchange_rate import ExchangeRateService
from api.services.ext.configurator import ConfiguratorService
from api.services.notification_manager import NotificationManager
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)

settings = Settings()
broker = TasksBroker(url=settings.redis_url).with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_url, keep_results=False)
)
client_tasks_broker = TasksBroker(url=settings.redis_url, queue_name="taskiq_client_tasks").with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_url, keep_results=False)
)
redis_scheduler_source = ListRedisScheduleSource(settings.redis_url)
label_scheduler_resource = LabelScheduleSource(broker)
scheduler = TaskiqScheduler(broker, sources=[label_scheduler_resource, redis_scheduler_source])
del settings


@broker.task("rates_action")
@inject(patch_module=True)
async def rates_action(
    params: RatesActionMessage,
    exchange_rate_service: FromDishka[ExchangeRateService],
) -> str:
    func = getattr(exchange_rate_service, params.func)
    return json.dumps(await func(*params.args), cls=utils.common.DecimalAwareJSONEncoder)


@broker.task("send_verification_email")
@inject(patch_module=True)
async def send_verification_email(params: SendVerificationEmailMessage, user_service: FromDishka[UserService]) -> None:
    user = await user_service.get_or_none(params.user_id)
    if not user:
        return
    await user_service.send_verification_email(user)


@broker.task("sync_wallet")
@inject(patch_module=True)
async def sync_wallet(
    params: SyncWalletMessage,
    wallet_service: FromDishka[WalletService],
    coin_service: FromDishka[CoinService],
    redis_pool: FromDishka[Redis],
    plugin_registry: FromDishka[PluginRegistry],
) -> None:
    model = await wallet_service.get_or_none(params.wallet_id)
    if not model:
        return
    coin = await coin_service.get_coin(
        model.currency, {"xpub": model.xpub, "contract": model.contract, **model.additional_xpub_data}
    )
    try:
        balance = await coin.balance()
    except Exception as e:
        logger.error(f"Wallet {model.id} failed to sync:\n{get_exception_message(e)}")
        await utils.redis.publish_message(redis_pool, f"wallet:{model.id}", {"status": "error", "balance": "0"})
        return
    await plugin_registry.run_hook("wallet_synced", model, balance)
    logger.info(f"Wallet {model.id} synced, balance: {balance['confirmed']}")
    await utils.redis.publish_message(
        redis_pool, f"wallet:{model.id}", {"status": "success", "balance": str(balance["confirmed"])}
    )


@broker.task("send_notification")
@inject(patch_module=True)
async def send_notification(
    params: SendNotificationMessage,
    notification_manager: FromDishka[NotificationManager],
    store_service: FromDishka[StoreService],
) -> None:
    store = await store_service.get_or_none(params.store_id)
    if not store:
        return
    await notification_manager.notify(store, params.text)


@broker.task("process_new_backup_policy")
@inject(patch_module=True)
async def process_new_backup_policy(params: ProcessNewBackupPolicyMessage, backup_manager: FromDishka[BackupManager]) -> None:
    await backup_manager.process_new_policy(params.old_policy, params.new_policy)


@broker.task("deploy_task")
@inject(patch_module=True)
async def deploy_task(params: DeployTaskMessage, configurator_service: FromDishka[ConfiguratorService]) -> None:
    return await configurator_service.run_deploy_task(params.task_id)


@broker.task("license_changed")
@inject(patch_module=True)
async def license_changed(params: LicenseChangedMessage, plugin_registry: FromDishka[PluginRegistry]) -> None:
    await plugin_registry.run_hook("license_changed", params.license_key, params.license_info)


# We need two tasks here due to the way taskiq works, with shared task it seems to execute only in one broker
# (the one which is set as default_broker)
@broker.task("plugin_task_server")
@inject(patch_module=True)
async def plugin_task_server(params: PluginTaskMessage, plugin_registry: FromDishka[PluginRegistry]) -> None:
    await plugin_registry.process_plugin_task(params)


@client_tasks_broker.task("plugin_task_client")
@inject(patch_module=True)
async def plugin_task_client(params: PluginTaskMessage, plugin_registry: FromDishka[PluginRegistry]) -> None:
    await plugin_registry.process_plugin_task(params)
