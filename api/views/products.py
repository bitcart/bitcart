import json
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Security, UploadFile
from fastapi.security import SecurityScopes
from pydantic import ValidationError
from sqlalchemy import distinct, func
from starlette.requests import Request

from api import crud, db, models, pagination, schemes, utils

router = APIRouter()


async def create_product(
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["product_management"]),
):
    filename = utils.files.get_image_filename(image)
    data = json.loads(data)
    try:
        data = schemes.CreateProduct(**data)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    data.image = filename
    d = data.dict()
    discounts = d.pop("discounts", None)
    with utils.database.safe_db_write():
        obj = await models.Product.create(**d, user_id=user.id)
        created = []
        for i in discounts:
            created.append((await models.DiscountxProduct.create(product_id=obj.id, discount_id=i)).discount_id)
        obj.discounts = created
        if image:
            filename = utils.files.get_image_filename(image, False, obj)
            await obj.update(image=filename).apply()
            await utils.files.save_image(filename, image)
    return obj


async def get_product_noauth(model_id: int, store: Optional[int] = None):
    query = models.Product.query.where(models.Product.id == model_id)
    if store is not None:
        query = query.where(models.Product.store_id == store)
    item = await query.gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
    await crud.products.product_add_related(item)
    return item


async def process_edit_product(model_id, data, image, user, patch=True):
    data = json.loads(data)
    try:
        model = schemes.Product(**data)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    item = await get_product_noauth(model_id)
    if image:
        filename = utils.files.get_image_filename(image, False, item)
        model.image = filename
        await utils.files.save_image(filename, image)
    else:
        utils.files.safe_remove(item.image)
        model.image = None
    with utils.database.safe_db_write():
        if patch:
            await item.update(**model.dict(exclude_unset=True)).apply()  # type: ignore
        else:
            await item.update(**model.dict()).apply()
    return item


async def patch_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["product_management"]),
):
    return await process_edit_product(model_id, data, image, user)


async def put_product(
    model_id: int,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["product_management"]),
):
    return await process_edit_product(model_id, data, image, user, patch=False)


async def delete_product(item: schemes.Product, user: schemes.User) -> schemes.Product:
    await crud.products.product_add_related(item)
    utils.files.safe_remove(item.image)
    await item.delete()
    return item


async def get_products(
    request: Request,
    pagination: pagination.Pagination = Depends(),
    store: Optional[int] = None,
    category: Optional[str] = "",
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
):
    try:
        user = await utils.authorization.AuthDependency()(request, SecurityScopes(["product_management"]))
    except HTTPException:
        if store is None:
            raise
        user = None
    return await pagination.paginate(
        models.Product,
        user.id if user else None,
        store,
        category,
        min_price,
        max_price,
        sale,
        postprocess=crud.products.products_add_related,
    )


@router.get("/maxprice")
async def get_max_product_price(store: int):
    return (
        await (
            models.Product.query.where(models.Product.store_id == store)
            .with_only_columns([db.db.func.max(distinct(models.Product.price))])
            .order_by(None)
            .gino.scalar()
        )
        or 0
    )


async def products_count(
    request: Request,
    store: Optional[int] = None,
    category: Optional[str] = "",
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
):
    query = models.Product.query
    if sale:
        query = (
            query.select_from(models.Product.join(models.DiscountxProduct).join(models.Discount))
            .having(func.count(models.DiscountxProduct.product_id) > 0)
            .where(models.Discount.end_date > utils.time.now())
        )
    if store is None:
        user = await utils.authorization.AuthDependency()(request, SecurityScopes(["product_management"]))
        query = query.where(models.Product.user_id == user.id)
    else:
        query = query.where(models.Product.store_id == store)
    if category and category != "all":
        query = query.where(models.Product.category == category)
    if min_price is not None:
        query = query.where(models.Product.price >= min_price)
    if max_price is not None:
        query = query.where(models.Product.price <= max_price)
    return await (query.with_only_columns([db.db.func.count(distinct(models.Product.id))]).order_by(None).gino.scalar()) or 0


@router.get("/categories")
async def categories(store: int):
    return {
        category
        for category, in await models.Product.select("category").where(models.Product.store_id == store).gino.all()
        if category
    }.union({"all"})


utils.routing.ModelView.register(
    router,
    "/",
    models.Product,
    schemes.Product,
    schemes.CreateProduct,
    custom_methods={"delete": delete_product},
    request_handlers={
        "get": get_products,
        "get_one": get_product_noauth,
        "post": create_product,
        "patch": patch_product,
        "put": put_product,
        "get_count": products_count,
    },
    scopes=["product_management"],
)
