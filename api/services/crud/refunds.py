from typing import cast

from dishka import AsyncContainer
from fastapi import HTTPException

from api import models
from api.db import AsyncSession
from api.exceptions import EmailSendError, RendererUnavailableError
from api.ext.moneyformat import currency_table
from api.invoices import InvoiceStatus
from api.logging import get_exception_details, get_exception_message, get_logger
from api.schemas.payouts import CreatePayout
from api.schemas.refunds import CreateRefund, RefundData, SubmitRefundData
from api.schemas.tasks import SendNotificationMessage
from api.services.crud import CRUDService
from api.services.crud.invoices import InvoiceService
from api.services.crud.payouts import PayoutService
from api.services.crud.repositories import RefundRepository
from api.services.crud.stores import StoreService
from api.services.crud.templates import TemplateService
from api.services.email import EmailService
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from api.types import TasksBroker

logger = get_logger(__name__)


class RefundService(CRUDService[models.Refund]):
    repository_type = RefundRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        invoice_service: InvoiceService,
        store_service: StoreService,
        template_service: TemplateService,
        payout_service: PayoutService,
        email_service: EmailService,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
        settings: Settings,
    ) -> None:
        super().__init__(session, container)
        self.invoice_service = invoice_service
        self.store_service = store_service
        self.template_service = template_service
        self.payout_service = payout_service
        self.email_service = email_service
        self.broker = broker
        self.plugin_registry = plugin_registry
        self.settings = settings

    async def create_refund(self, data: RefundData, invoice_id: str, user: models.User) -> models.Refund:
        invoice = await self.invoice_service.get(invoice_id, user)
        if not invoice.payment_id:
            raise HTTPException(422, "Can't refund unpaid invoice")
        payment = cast(models.PaymentMethod, self.invoice_service.match_payment(invoice.payments, invoice.payment_id))
        refund = await self.create(
            CreateRefund(
                amount=currency_table.round_received(data.currency, data.amount),
                currency=data.currency,
                wallet_id=cast(str, payment.wallet_id),
                invoice_id=invoice.id,
            ),
            user,
        )
        if data.send_email and invoice.buyer_email:
            store = await self.store_service.get(invoice.store_id)
            if self.email_service.is_enabled(store.email_settings):
                refund_url = f"{self.settings.checkout_url}/refunds/{refund.id}"
                await self._email_refund(store, invoice, refund, refund_url, invoice.buyer_email)
        return refund

    async def _email_refund(
        self, store: models.Store, invoice: models.Invoice, refund: models.Refund, refund_url: str, buyer_email: str
    ) -> None:
        try:
            message = await self.template_service.render_customer_refund(store, invoice, refund, refund_url)
        except RendererUnavailableError as e:
            logger.error(f"Refund {refund.id}: failed to render the buyer email: {get_exception_details(e)}")
            return
        message = await self.plugin_registry.apply_filters(
            "refund_customer_message", message, store, invoice, refund, refund_url
        )
        try:
            await self.email_service.send(
                store.email_settings,
                buyer_email,
                f"Refund for invoice {invoice.id}",
                message.text,
                html=message.is_html,
            )
        except EmailSendError as e:
            logger.warning(f"Refund {refund.id}: failed to email the buyer: {get_exception_message(e)}")

    async def submit_refund(self, refund_id: str, data: SubmitRefundData) -> models.Refund:
        refund = await self.get(refund_id, atomic_update=True)
        if refund.payout_id:
            raise HTTPException(422, "Refund already submitted")
        if not refund.invoice_id:
            raise HTTPException(422, "Refund invoice was deleted")
        invoice = await self.invoice_service.get(refund.invoice_id)
        payout_data = CreatePayout(
            amount=refund.amount,
            currency=refund.currency,
            destination=data.destination,
            store_id=cast(str, invoice.store_id),
            wallet_id=cast(str, refund.wallet_id),
        ).model_dump()
        payout_data["user_id"] = refund.user_id
        payout = await self.payout_service.create(payout_data)
        refund.update(payout=payout, destination=data.destination)
        try:
            notification = await self.template_service.render_merchant_refund_notify(invoice.store, invoice, refund)
        except RendererUnavailableError as e:
            logger.error(f"Refund {refund.id}: failed to render the store notification: {get_exception_details(e)}")
            return refund
        await self.broker.publish(
            "send_notification",
            SendNotificationMessage(store_id=cast(str, invoice.store_id), text=notification.text),
        )
        return refund

    async def process_sent_payout(self, payout: models.Payout) -> None:
        refund = await self.get_or_none(None, payout_id=payout.id)
        # Refunds: mark invoice as refunded if there's a matching object
        if refund and refund.invoice_id:
            invoice = await self.invoice_service.get(refund.invoice_id)
            await self.invoice_service.update_status(invoice, InvoiceStatus.REFUNDED)
