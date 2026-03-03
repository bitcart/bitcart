from datetime import datetime
from typing import cast

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncScalarResult
from sqlalchemy.orm import selectinload

from api import models
from api.invoices import PAID_STATUSES, InvoiceStatus
from api.services.crud.repository import CRUDRepository


class PaymentMethodRepository(CRUDRepository[models.PaymentMethod]):
    model_type = models.PaymentMethod

    async def get_info_by_id(self, payment_id: str) -> tuple[models.PaymentMethod, models.Wallet] | None:
        fetch_data = (
            await self.session.execute(
                select(models.PaymentMethod, models.Wallet)
                .where(models.Wallet.id == models.PaymentMethod.wallet_id)
                .where(models.PaymentMethod.id == payment_id)
            )
        ).first()
        if not fetch_data:
            return None
        return cast(tuple[models.PaymentMethod, models.Wallet], fetch_data)


class InvoiceRepository(CRUDRepository[models.Invoice]):
    model_type = models.Invoice

    LOAD_OPTIONS = [
        selectinload(models.Invoice.products_associations).subqueryload(models.ProductxInvoice.product),
        selectinload(models.Invoice.payments),
        selectinload(models.Invoice.store).subqueryload(models.Store.notifications),
        selectinload(models.Invoice.refunds),
    ]

    async def get_invoices_for_expiry(self, now: datetime) -> AsyncScalarResult[models.Invoice]:
        return await self.session.stream_scalars(
            select(models.Invoice)
            .where(models.Invoice.status == InvoiceStatus.PENDING)
            .where(models.Invoice.created + func.make_interval(0, 0, 0, 0, 0, models.Invoice.expiration) <= now)  # in minutes
        )

    async def get_complete_grouped_total_price(
        self, *, eth_based: bool = False, eth_based_currencies: list[str] | None = None
    ) -> dict[str, str]:
        query = (
            select(models.Invoice.currency, func.sum(models.Invoice.sent_amount * models.PaymentMethod.rate))
            .where(models.Invoice.status.in_(PAID_STATUSES))
            .where(models.Invoice.id == models.PaymentMethod.invoice_id)
            .where(models.PaymentMethod.is_used.is_(True))
            .where(models.Invoice.sent_amount.is_not(None))
            .where(func.cardinality(models.Invoice.tx_hashes) > 0)
            .where(models.PaymentMethod.rate != 0)
            .group_by(models.Invoice.currency)
        )
        if eth_based and eth_based_currencies:
            query = query.where(models.PaymentMethod.currency.in_(eth_based_currencies))
        total_price_results = (await self.session.execute(query)).all()
        return {currency: str(price) for currency, price in total_price_results}

    async def get_average_methods_number(self) -> int:
        subquery = (
            select(models.PaymentMethod)
            .where(models.PaymentMethod.invoice_id == models.Invoice.id)
            .with_only_columns(func.count(distinct(models.PaymentMethod.id)).label("count"))
            .group_by(models.Invoice.id)
            .alias("table")
        )
        return int((await self.session.execute(select(func.avg(subquery.c.count)).select_from(subquery))).scalar() or 0)

    async def get_average_paid_time(self) -> float:
        return (
            (
                await self.session.execute(
                    select(func.avg(func.extract("epoch", (models.Invoice.paid_date - models.Invoice.created))))
                )
            ).scalar()
            or 0
        ) / 60

    async def get_status_counts(self) -> dict[str, int]:
        status_results = cast(
            list[tuple[str, int]],
            (
                await self.session.execute(
                    select(models.Invoice.status, func.count(models.Invoice.id)).group_by(models.Invoice.status)
                )
            ).all(),
        )
        return dict(status_results)
