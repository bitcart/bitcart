import os
from decimal import Decimal
from typing import Any, cast

import aiofiles
from advanced_alchemy.filters import StatementFilter
from fastapi import UploadFile
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import selectinload

from api import models, utils
from api.db import AsyncSession
from api.schemas.products import CreateProduct, UpdateProduct
from api.services.crud import CRUDService
from api.services.crud.repositories import DiscountRepository, ProductRepository
from api.settings import Settings


class ProductService(CRUDService[models.Product]):
    repository_type = ProductRepository

    LOAD_OPTIONS = [selectinload(models.Product.discounts), selectinload(models.Product.store)]

    def __init__(self, session: AsyncSession, discount_repository: DiscountRepository, settings: Settings) -> None:
        super().__init__(session)
        self.settings = settings
        self.discount_repository = discount_repository

    async def prepare_create(self, data: dict[str, Any], user: models.User | None = None) -> dict[str, Any]:
        data = await super().prepare_create(data, user)
        data["status"] = "active"
        return data

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        await self._process_many_to_many_field(data, "discounts", self.discount_repository)
        return data

    @staticmethod
    def _filter_in_product(
        store_id: str | None,
        category: str | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        sale: bool | None,
    ) -> tuple[Select[tuple[models.Product]] | None, list[StatementFilter | ColumnElement[bool]]]:
        filters: list[StatementFilter | ColumnElement[bool]] = []
        statement: Select[tuple[models.Product]] | None = None
        if sale:
            statement = (
                select(models.Product)
                .join(models.DiscountxProduct)
                .join(models.Discount)
                .having(func.count(models.DiscountxProduct.product_id) > 0)
                .where(models.Discount.end_date > utils.time.now())
            )
        if store_id is not None:
            filters.append(models.Product.store_id == store_id)
        if category and category != "all":
            filters.append(models.Product.category == category)
        if min_price is not None:
            filters.append(models.Product.price >= min_price)
        if max_price is not None:
            filters.append(models.Product.price <= max_price)
        return statement, filters

    async def get_all_categories(self, store_id: str) -> list[str]:
        query = select(models.Product.category).where(models.Product.store_id == store_id)
        result = (await self.session.execute(query)).all()
        dataset = {category for (category,) in result if category}
        dataset.discard("all")
        return ["all"] + sorted(dataset)

    async def get_max_product_price(self, store_id: str) -> Decimal:
        return cast(
            Decimal,
            await utils.database.get_scalar(
                self.session, select(models.Product).where(models.Product.store_id == store_id), func.max, models.Product.price
            ),
        )

    async def get(
        self, item_id: Any, user: models.User | None = None, store_id: str | None = None, *args: Any, **kwargs: Any
    ) -> models.Product:
        query = select(models.Product).where(models.Product.id == item_id)
        if store_id is not None:
            query = query.where(models.Product.store_id == store_id)
        return await super().get(item_id, user, *args, statement=query, **kwargs)

    async def update_stock_levels(self, invoice: models.Invoice) -> None:
        quantities = (
            await self.session.execute(
                select(models.Product, models.ProductxInvoice.count)
                .where(models.ProductxInvoice.product_id == models.Product.id)
                .where(models.ProductxInvoice.invoice_id == invoice.id)
            )
        ).all()
        # TODO: make it sql-only
        for product, quantity in quantities:
            if product.quantity == -1:  # unlimited quantity
                continue
            product.quantity = max(0, product.quantity - quantity)

    @classmethod
    def get_image_filename(cls, model_id: str) -> str:
        return f"images/products/{model_id}.png"

    def get_image_local_path(self, model_id: str) -> str:
        return os.path.join(self.settings.products_image_dir, f"{model_id}.png")

    async def save_image(self, model: models.Product, image: UploadFile) -> None:
        filename = self.get_image_local_path(model.id)
        async with aiofiles.open(filename, "wb") as f:
            await f.write(await image.read())

    def remove_image(self, model: models.Product) -> None:
        utils.files.safe_remove(self.get_image_local_path(model.id))

    async def create_with_image(self, schema: CreateProduct, user: models.User, image: UploadFile) -> models.Product:
        data = schema.model_dump()
        data["id"] = utils.common.unique_id()
        data["image"] = self.get_image_filename(data["id"]) if image else ""
        obj = await self.create(data, user)
        if image:
            await self.save_image(obj, image)
        return obj

    async def update_with_image(
        self, schema: UpdateProduct, item_id: str, user: models.User, image: UploadFile
    ) -> models.Product:
        item = await self.get(item_id, user)
        if image:
            filename = self.get_image_filename(item.id)
            schema.image = filename
            await self.save_image(item, image)
        else:
            self.remove_image(item)
            schema.image = ""
        return await self.update(schema, item_id, user)

    async def delete(self, item: models.Product | str, user: models.User | None = None) -> models.Product:
        item = await super().delete(item, user)
        self.remove_image(item)
        return item

    async def delete_many(self, ids: list[str], user: models.User | None = None) -> list[models.Product]:
        items = await super().delete_many(ids, user)
        for item in items:
            self.remove_image(item)
        return items
