from typing import cast
from urllib.parse import urljoin

from fastapi import HTTPException
from sqlalchemy.orm import selectinload

from api import models, utils
from api.db import AsyncSession
from api.ext.moneyformat import currency_table
from api.invoices import InvoiceStatus
from api.schemas.payouts import CreatePayout
from api.schemas.refunds import CreateRefund, RefundData, SubmitRefundData
from api.schemas.tasks import SendNotificationMessage
from api.services.crud import CRUDService
from api.services.crud.invoices import InvoiceService
from api.services.crud.payouts import PayoutService
from api.services.crud.repositories import RefundRepository
from api.services.crud.stores import StoreService
from api.services.crud.templates import TemplateService
from api.services.plugin_registry import PluginRegistry
from api.types import TasksBroker


class RefundService(CRUDService[models.Refund]):
    repository_type = RefundRepository

    LOAD_OPTIONS = [selectinload(models.Refund.payout).subqueryload(models.Payout.wallet)]

    def __init__(
        self,
        session: AsyncSession,
        invoice_service: InvoiceService,
        store_service: StoreService,
        template_service: TemplateService,
        payout_service: PayoutService,
        broker: TasksBroker,
        plugin_registry: PluginRegistry,
    ) -> None:
        super().__init__(session)
        self.invoice_service = invoice_service
        self.store_service = store_service
        self.template_service = template_service
        self.payout_service = payout_service
        self.broker = broker
        self.plugin_registry = plugin_registry

    async def create_refund(self, data: RefundData, invoice_id: str, user: models.User) -> models.Refund:
        invoice = await self.invoice_service.get(invoice_id, user)
        if not invoice.payment_id:
            raise HTTPException(422, "Can't refund unpaid invoice")
        payment = cast(models.PaymentMethod, self.invoice_service.match_payment(invoice.payments, invoice.payment_id))
        refund = await self.create(
            CreateRefund(
                amount=data.amount, currency=data.currency, wallet_id=cast(str, payment.wallet_id), invoice_id=invoice.id
            ),
            user,
        )
        if data.send_email and invoice.buyer_email:
            store = await self.store_service.get(invoice.store_id)
            if (email_obj := utils.email.StoreEmail.get_email(store)).is_enabled():
                refund_url = urljoin(data.admin_host, f"/refunds/{refund.id}")
                refund.amount = currency_table.normalize(refund.currency, refund.amount)
                refund_template = await self.plugin_registry.apply_filters(
                    "refund_customer_text",
                    await self.template_service.get_customer_refund_template(store, invoice, refund, refund_url),
                    store,
                    invoice,
                    refund,
                    refund_url,
                )
                email_obj.send_mail(invoice.buyer_email, refund_template, f"Refund for invoice {invoice.id}")
        return refund

    async def submit_refund(self, refund_id: str, data: SubmitRefundData) -> models.Refund:
        refund = await self.get(refund_id, atomic_update=True)
        if refund.payout_id:
            raise HTTPException(422, "Refund already submitted")
        invoice = await self.invoice_service.get(refund.invoice_id)
        payout_data = CreatePayout(
            amount=refund.amount,
            currency=refund.currency,
            destination=data.destination,
            store_id=cast(str, invoice.store_id),
            wallet_id=cast(str, refund.wallet_id),
        ).model_dump()
        payout_data["user_id"] = refund.user_id
        payout = await self.payout_service.create(payout_data)  # TODO: maybe we need to pass user here for validation?
        refund.update(
            payout=payout, destination=data.destination, amount=currency_table.normalize(refund.currency, refund.amount)
        )
        await self.broker.publish(
            SendNotificationMessage(
                store_id=cast(str, invoice.store_id),
                text=await self.template_service.get_merchant_refund_notify_template(invoice.store, invoice, refund),
            ),
            "send_notification",
        )
        return refund

    async def process_sent_payout(self, payout: models.Payout) -> None:
        refund = await self.get_or_none(None, payout_id=payout.id)
        # Refunds: mark invoice as refunded if there's a matching object
        if refund:
            invoice = await self.invoice_service.get(refund.invoice_id)
            if invoice:
                await self.invoice_service.update_status(invoice, InvoiceStatus.REFUNDED)
