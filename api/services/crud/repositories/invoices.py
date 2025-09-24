from datetime import datetime
from typing import cast

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncScalarResult
from sqlalchemy.orm import selectinload

from api import models
from api.invoices import InvoiceStatus
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
    ]

    async def get_invoices_for_expiry(self, now: datetime) -> AsyncScalarResult[models.Invoice]:
        return await self.session.stream_scalars(
            select(models.Invoice)
            .where(models.Invoice.status == InvoiceStatus.PENDING)
            .where(models.Invoice.created + func.make_interval(0, 0, 0, 0, 0, models.Invoice.expiration) <= now)  # in minutes
        )

    async def get_complete_grouped_total_price(self) -> dict[str, str]:
        total_price_results = (
            await self.session.execute(
                select(models.Invoice.currency, func.sum(models.Invoice.price))
                .where(models.Invoice.status == "complete")
                .where(func.cardinality(models.Invoice.tx_hashes) > 0)
                .group_by(models.Invoice.currency)
            )
        ).all()
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
