from collections.abc import AsyncIterator

from dishka import Provider, Scope, decorate, provide, provide_all

from api.services.auth import AuthService
from api.services.backup_manager import BackupManager
from api.services.coins import CoinService
from api.services.crud.discounts import DiscountService
from api.services.crud.files import FileService
from api.services.crud.invoices import InvoiceService
from api.services.crud.notifications import NotificationService
from api.services.crud.payouts import PayoutService
from api.services.crud.products import ProductService
from api.services.crud.refunds import RefundService
from api.services.crud.stores import StoreService
from api.services.crud.templates import TemplateService
from api.services.crud.tokens import TokenService
from api.services.crud.users import UserService
from api.services.crud.wallets import WalletService
from api.services.exchange_rate import ExchangeRateService
from api.services.ext.configurator import ConfiguratorService
from api.services.ext.tor import TorService
from api.services.ext.update import UpdateCheckService
from api.services.health_check import HealthCheckService
from api.services.ipn_sender import IPNSender
from api.services.metrics_service import MetricsService
from api.services.notification_manager import NotificationManager
from api.services.payment_processor import PaymentProcessor
from api.services.payout_manager import PayoutManager
from api.services.plugin_manager import PluginManager
from api.services.plugin_registry import PluginRegistry
from api.services.server_manager import ServerManager
from api.services.settings import SettingService
from api.services.wallet_data import WalletDataService
from api.types import AuthServiceProtocol


class ServicesProvider(Provider):
    request_provides = provide_all(
        UserService,
        WalletService,
        NotificationService,
        TemplateService,
        StoreService,
        DiscountService,
        ProductService,
        InvoiceService,
        PayoutService,
        TokenService,
        SettingService,
        ServerManager,
        FileService,
        RefundService,
        scope=Scope.SESSION,
    )
    auth_service = provide(AuthService, scope=Scope.SESSION)
    auth_service_protocol = provide(AuthService, provides=AuthServiceProtocol, scope=Scope.SESSION)
    metrics_service = provide(MetricsService, scope=Scope.SESSION)

    app_provides = provide_all(
        CoinService,
        TorService,
        UpdateCheckService,
        PluginManager,
        PluginRegistry,
        ExchangeRateService,
        PaymentProcessor,
        PayoutManager,
        IPNSender,
        BackupManager,
        ConfiguratorService,
        NotificationManager,
        WalletDataService,
        HealthCheckService,
        scope=Scope.APP,  # for tests isolation
    )

    @decorate
    async def get_plugin_manager(
        self,
        service: PluginManager,
    ) -> AsyncIterator[PluginManager]:
        await service.start()
        yield service

    TO_PRELOAD = [PluginManager]
