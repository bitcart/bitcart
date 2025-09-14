from collections.abc import AsyncIterator

from dishka import Provider, decorate

from api.ioc.services import ServicesProvider
from api.services.backup_manager import BackupManager
from api.services.exchange_rate import ExchangeRateService
from api.services.ext.configurator import ConfiguratorService
from api.services.ext.tor import TorService
from api.services.ext.update import UpdateCheckService
from api.services.payment_processor import PaymentProcessor


class WorkerProvider(Provider):
    @decorate
    async def get_exchange_rate_service(
        self,
        service: ExchangeRateService,
    ) -> AsyncIterator[ExchangeRateService]:
        await service.start()
        yield service

    @decorate
    async def get_payment_processor(
        self,
        service: PaymentProcessor,
    ) -> AsyncIterator[PaymentProcessor]:
        await service.start()
        yield service

    @decorate
    async def get_tor_service(
        self,
        service: TorService,
    ) -> AsyncIterator[TorService]:
        await service.start()
        yield service

    @decorate
    async def get_backup_manager(
        self,
        service: BackupManager,
    ) -> AsyncIterator[BackupManager]:
        await service.start()
        yield service

    @decorate
    async def get_configurator_service(
        self,
        service: ConfiguratorService,
    ) -> AsyncIterator[ConfiguratorService]:
        await service.start()
        yield service

    @decorate
    async def get_update_check_service(
        self,
        service: UpdateCheckService,
    ) -> AsyncIterator[UpdateCheckService]:
        await service.start()
        yield service

    # ExchangeRateService not preloaded to avoid rate limits during develop
    TO_PRELOAD = ServicesProvider.TO_PRELOAD + [
        PaymentProcessor,
        TorService,
        BackupManager,
        ConfiguratorService,
        UpdateCheckService,
    ]
