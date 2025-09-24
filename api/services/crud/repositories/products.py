from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api import models
from api.services.crud.repository import CRUDRepository


class ProductRepository(CRUDRepository[models.Product]):
    model_type = models.Product

    LOAD_OPTIONS = [selectinload(models.Product.discounts), selectinload(models.Product.store)]

    async def get_quantities(self, products: dict[str, int]) -> tuple[tuple[str, str, int]]:
        return cast(
            tuple[tuple[str, str, int]],
            (
                await self.session.execute(
                    select(models.Product.id, models.Product.name, models.Product.quantity).where(
                        models.Product.id.in_(list(products.keys()))
                    )
                )
            ).all(),
        )

    async def get_products_categories(self, store_id: str) -> tuple[tuple[str | None]]:
        query = select(models.Product.category).where(models.Product.store_id == store_id)
        result = (await self.session.execute(query)).all()
        return cast(tuple[tuple[str | None]], result)

    async def find_invoice_products(self, invoice_id: str) -> tuple[tuple[models.Product, int]]:
        return cast(
            tuple[tuple[models.Product, int]],
            (
                await self.session.execute(
                    select(models.Product, models.ProductxInvoice.count)
                    .where(models.ProductxInvoice.product_id == models.Product.id)
                    .where(models.ProductxInvoice.invoice_id == invoice_id)
                )
            ).all(),
        )
        # TODO: make it sql-only
