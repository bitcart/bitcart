import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Coroutine
from decimal import Decimal
from typing import Any, Protocol, cast

from bitcart import (  # type: ignore[attr-defined]
    BTC,
    errors,
)
from dishka import AsyncContainer, Scope
from sqlalchemy import ColumnElement, Select, or_, select

from api import constants, models, utils
from api.db import AsyncSession
from api.invoices import DEFAULT_PENDING_STATUSES, InvoiceExceptionStatus, InvoiceStatus, convert_status
from api.logging import get_logger, log_errors
from api.services.coins import CoinService
from api.services.crud.invoices import InvoiceService
from api.services.crud.repositories.invoices import InvoiceRepository
from api.services.payout_manager import PayoutManager
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings

logger = get_logger(__name__)


class ProcessPendingFunc(Protocol):
    async def __call__(
        self,
        invoice: models.Invoice,
        method: models.PaymentMethod,
        wallet: models.Wallet,
        status: str,
        tx_hashes: list[str],
        sent_amount: Decimal,
        *,
        di_context: AsyncContainer,
    ) -> bool: ...


class PaymentProcessor:
    def __init__(
        self,
        container: AsyncContainer,
        coin_service: CoinService,
        settings: Settings,
        payout_manager: PayoutManager,
        plugin_registry: PluginRegistry,
    ) -> None:
        self.container = container
        self.coin_service = coin_service
        self.settings = settings
        self.payout_manager = payout_manager
        self.plugin_registry = plugin_registry
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.register_handlers()

    def register_handlers(self) -> None:
        self.coin_service.manager.add_event_handler("new_payment", self.new_payment_handler)
        self.coin_service.manager.add_event_handler("new_block", self.new_block_handler)

    async def new_payment_handler(
        self,
        instance: BTC,
        event: str,
        address: str,
        status: str,
        status_str: str,
        tx_hashes: list[str] | None = None,
        sent_amount: Decimal = Decimal(0),
        contract: str | None = None,
    ) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            session = await container.get(AsyncSession)
            invoice_service = await container.get(InvoiceService)
            if tx_hashes is None:
                tx_hashes = []
            with log_errors(logger):
                sent_amount = Decimal(sent_amount)
                query = self.get_pending_invoices_query(instance.coin_name.lower()).where(
                    models.PaymentMethod.lookup_field == address
                )
                if contract:
                    query = query.where(models.PaymentMethod.contract == contract)
                data = (await session.execute(query.with_for_update())).first()
                if not data:  # received payment but no matching invoice
                    return
                method, invoice, wallet = data
                await invoice_service.load_one(invoice)
                await self.plugin_registry.run_hook(
                    "new_payment", invoice, method, wallet, status, status_str, tx_hashes, sent_amount
                )
                await self.process_electrum_status(
                    invoice,
                    method,
                    wallet,
                    status,
                    tx_hashes,
                    sent_amount,
                    di_context=container,
                )

    async def iterate_pending_invoices(
        self, session: AsyncSession, invoice_service: InvoiceService, currency: str, statuses: list[str] | None = None
    ) -> AsyncIterator[tuple[models.PaymentMethod, models.Invoice, models.Wallet]]:
        with log_errors(logger):  # connection issues
            result = await session.stream(self.get_pending_invoices_query(currency, statuses=statuses))
            async for method, invoice, wallet in result:
                await invoice_service.load_one(invoice)
                yield method, invoice, wallet

    async def update_invoice_confirmations(
        self,
        invoice: models.Invoice,
        method: models.PaymentMethod,
        confirmations: int,
        tx_hashes: list[str],
        sent_amount: Decimal,
        wallet: models.Wallet,
        *,
        di_context: AsyncContainer,
    ) -> None:
        invoice_service = await di_context.get(InvoiceService)
        await invoice_service.update_confirmations(
            invoice, method, wallet, confirmations=confirmations, tx_hashes=tx_hashes, sent_amount=sent_amount
        )

    async def new_block_handler(self, instance: BTC, event: str, height: int) -> None:
        async with self.locks["new_block"], self.container(scope=Scope.REQUEST) as container:
            session = await container.get(AsyncSession)
            invoice_service = await container.get(InvoiceService)
            coros = []
            coros.append(self.payout_manager.process_new_block(instance.coin_name.lower()))
            async for method, invoice, wallet in self.iterate_pending_invoices(
                session, invoice_service, instance.coin_name.lower(), statuses=[InvoiceStatus.CONFIRMED]
            ):
                with log_errors(logger):  # issues processing one item
                    if invoice.status != InvoiceStatus.CONFIRMED or method.id != invoice.payment_id or method.lightning:
                        continue
                    confirmations = await self.get_confirmations(method, wallet)
                    if confirmations != method.confirmations:
                        coros.append(
                            utils.common.concurrent_safe_run(
                                self.update_invoice_confirmations,
                                invoice,
                                method,
                                confirmations,
                                invoice.tx_hashes,
                                cast(Decimal, invoice.sent_amount),
                                wallet,
                                container=self.container,
                                logger=logger,
                            )
                        )
            coros.append(self.plugin_registry.run_hook("new_block", instance.coin_name.lower(), height))
            # NOTE: if another operation in progress exception occurs, make it await one by one
            await asyncio.gather(*coros)

    async def process_electrum_status(
        self,
        invoice: models.Invoice,
        method: models.PaymentMethod,
        wallet: models.Wallet,
        status: str,
        tx_hashes: list[str],
        sent_amount: Decimal,
        *,
        di_context: AsyncContainer,
    ) -> bool:
        invoice_service = await di_context.get(InvoiceService)
        electrum_status = convert_status(status)
        if invoice.status not in DEFAULT_PENDING_STATUSES:  # double-check
            return False
        if electrum_status == InvoiceStatus.PENDING and sent_amount > 0:
            await invoice_service.update_status(invoice, InvoiceStatus.PENDING, method, tx_hashes, sent_amount)
        if electrum_status == InvoiceStatus.UNCONFIRMED:  # for on-chain invoices only
            await invoice_service.update_status(invoice, InvoiceStatus.PAID, method, tx_hashes, sent_amount)
            await invoice_service.update_confirmations(
                invoice, method, wallet, confirmations=0, tx_hashes=tx_hashes, sent_amount=sent_amount
            )  # to trigger complete for stores accepting 0-conf
        if electrum_status == InvoiceStatus.COMPLETE:  # for paid lightning invoices or confirmed on-chain invoices
            if method.lightning:
                await invoice_service.update_status(invoice, InvoiceStatus.COMPLETE, method, tx_hashes, sent_amount)
            else:
                await invoice_service.update_confirmations(
                    invoice,
                    method,
                    wallet,
                    confirmations=await self.get_confirmations(method, wallet),
                    tx_hashes=tx_hashes,
                    sent_amount=sent_amount,
                )
        return True

    async def check_pending(
        self,
        currency: str,
        process_func: ProcessPendingFunc | None = None,
    ) -> None:
        if process_func is None:
            process_func = self.process_electrum_status
        async with self.container(scope=Scope.REQUEST) as container:
            session = await container.get(AsyncSession)
            invoice_service = await container.get(InvoiceService)
            await self.plugin_registry.run_hook("check_pending", currency)
            coros: list[Coroutine[Any, Any, Any]] = []
            coros.append(self.payout_manager.process_new_block(currency.lower()))
            async for method, invoice, wallet in self.iterate_pending_invoices(session, invoice_service, currency):
                with log_errors(logger):  # issues processing one item
                    if invoice.status == InvoiceStatus.EXPIRED:
                        continue
                    coin = await self.coin_service.get_coin(
                        method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
                    )
                    try:
                        if method.lightning:
                            invoice_data = await coin.get_invoice(method.lookup_field)
                        else:
                            invoice_data = await self.get_request(coin, method)
                    except errors.RequestNotFoundError:  # type: ignore # invoice dropped from mempool
                        await invoice_service.update_status(
                            invoice, InvoiceStatus.INVALID, set_exception_status=InvoiceExceptionStatus.FAILED_CONFIRM
                        )
                        continue
                    coros.append(
                        utils.common.concurrent_safe_run(
                            process_func,
                            invoice,
                            method,
                            wallet,
                            invoice_data["status"],
                            invoice_data.get("tx_hashes", []),
                            Decimal(invoice_data.get("sent_amount", 0)),
                            container=self.container,
                            logger=logger,
                        )
                    )
            await asyncio.gather(*coros)

    async def start(self) -> None:
        asyncio.create_task(self.manage_invoice_expiration())
        asyncio.create_task(
            self.coin_service.manager.start_websocket(reconnect_callback=self.check_pending, force_connect=True)
        )

    @classmethod
    def get_pending_invoice_statuses(cls, statuses: list[str] | None = None) -> ColumnElement[bool]:
        statuses = statuses or DEFAULT_PENDING_STATUSES
        return or_(
            *(models.Invoice.status == status for status in statuses),
        )

    @classmethod
    def get_pending_invoices_query(  # TODO: move to invoices repository
        cls, currency: str, statuses: list[str] | None = None
    ) -> Select[tuple[models.PaymentMethod, models.Invoice, models.Wallet]]:
        return (
            select(
                models.PaymentMethod,
                models.Invoice,
                models.Wallet,
            )
            .where(models.PaymentMethod.invoice_id == models.Invoice.id)
            .where(models.PaymentMethod.wallet_id == models.Wallet.id)
            .where(cls.get_pending_invoice_statuses(statuses=statuses))
            .where(models.PaymentMethod.currency == currency.lower())
            .where(models.Wallet.currency == models.PaymentMethod.currency)
            .order_by(models.PaymentMethod.created)
            .options(*InvoiceRepository.LOAD_OPTIONS)
        )

    async def get_request(self, coin: BTC, method: models.PaymentMethod) -> dict[str, Any]:
        if result := await self.plugin_registry.apply_filters("get_request", None, coin, method):
            return result
        return await coin.get_request(method.lookup_field)

    async def get_confirmations(self, method: models.PaymentMethod, wallet: models.Wallet) -> int:
        coin = await self.coin_service.get_coin(
            method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
        )
        invoice_data = await self.get_request(coin, method)
        return min(
            constants.MAX_CONFIRMATION_WATCH, invoice_data.get("confirmations", 0)
        )  # don't store arbitrary number of confirmations

    async def process_expire_task(self, invoice: models.Invoice, *, di_context: AsyncContainer) -> None:
        invoice_service = await di_context.get(InvoiceService)
        invoice = await invoice_service.get(invoice.id)
        if invoice.status == InvoiceStatus.PENDING:  # to ensure there are no duplicate notifications
            await invoice_service.update_status(invoice, InvoiceStatus.EXPIRED)
            await self.plugin_registry.run_hook("invoice_expired", invoice)

    async def manage_invoice_expiration(self) -> None:
        while True:
            async with self.container(scope=Scope.REQUEST) as container:
                invoice_repository = await container.get(InvoiceRepository)
                now = utils.time.now()
                with log_errors(logger):
                    result = await invoice_repository.get_invoices_for_expiry(now)
                    async for invoice in result:
                        with log_errors(logger):
                            asyncio.create_task(
                                utils.common.concurrent_safe_run(
                                    self.process_expire_task, invoice, container=self.container, logger=logger
                                )
                            )
            await asyncio.sleep(0.1)
