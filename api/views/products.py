import json
import os
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Security, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from starlette.requests import Request

from api import db, models, pagination, schemes, settings, utils

router = APIRouter()

OptionalProductScheme = utils.schemes.to_optional(schemes.Product)


def get_image_filename(model_id):
    return f"images/products/{model_id}.png"


def get_image_local_path(model_id):
    return os.path.join(settings.settings.products_image_dir, f"{model_id}.png")


async def save_image(model, image):
    filename = get_image_local_path(model.id)
    with open(filename, "wb") as f:
        f.write(await image.read())


def parse_data(data, scheme):
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        raise HTTPException(422, "Invalid JSON")
    try:
        data = scheme(**data)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    return data


async def create_product(
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["product_management"]),
):
    data = parse_data(data, schemes.CreateProduct)
    kwargs = utils.database.prepare_create_kwargs(models.Product, data, user)
    kwargs["image"] = get_image_filename(kwargs["id"]) if image else None
    obj = await utils.database.create_object_core(models.Product, kwargs)
    if image:
        await save_image(obj, image)
    return obj


async def get_product_noauth(model_id: str, store: Optional[str] = None):
    query = models.Product.query.where(models.Product.id == model_id)
    if store is not None:
        query = query.where(models.Product.store_id == store)
    item = await utils.database.get_object(models.Product, model_id, custom_query=query)
    return item


async def patch_product(
    model_id: str,
    data: str = Form(...),
    image: UploadFile = File(None),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["product_management"]),
):
    data = parse_data(data, OptionalProductScheme)
    item = await utils.database.get_object(models.Product, model_id, user)
    if image:
        filename = get_image_filename(item.id)
        data.image = filename
        await save_image(item, image)
    else:
        utils.files.safe_remove(get_image_local_path(item.id))
        data.image = None
    data = data.dict(exclude_unset=True)
    await utils.database.modify_object(item, data)
    return item


async def delete_product(item: schemes.Product, user: schemes.User) -> schemes.Product:
    utils.files.safe_remove(get_image_local_path(item.id))
    await item.delete()
    return item


async def get_products(
    request: Request,
    pagination: pagination.Pagination = Depends(),
    store: Optional[str] = None,
    category: Optional[str] = "",
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
    user: Optional[models.User] = Security(utils.authorization.optional_auth_dependency, scopes=["product_management"]),
):
    if not user and store is None:
        raise HTTPException(401, "Unauthorized")
    params = utils.common.prepare_query_params(request, custom_params=("store", "category", "min_price", "max_price", "sale"))
    return await utils.database.paginate_object(
        models.Product, pagination, user, store, category, min_price, max_price, sale, **params
    )


@router.get("/maxprice")
async def get_max_product_price(store: str):
    return await utils.database.get_scalar(
        models.Product.query.where(models.Product.store_id == store), db.db.func.max, models.Product.price
    )


async def products_count(
    request: Request,
    pagination: pagination.Pagination = Depends(),
    store: Optional[str] = None,
    category: Optional[str] = "",
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    sale: Optional[bool] = False,
    user: Optional[models.User] = Security(utils.authorization.optional_auth_dependency, scopes=["product_management"]),
):
    if store is None and not user:
        raise HTTPException(401, "Unauthorized")
    return await utils.database.paginate_object(
        models.Product, pagination, user, store, category, min_price, max_price, sale, count_only=True
    )


@router.get("/categories")
async def categories(store: str):
    dataset = {
        category
        for category, in await models.Product.select("category").where(models.Product.store_id == store).gino.all()
        if category
    }
    dataset.discard("all")
    return ["all"] + sorted(dataset)


async def batch_product_action(query, batch_settings: schemes.BatchSettings, user: schemes.User):
    if batch_settings.command == "delete":
        for (product_id,) in await select([models.Product.id]).where(models.Product.id.in_(batch_settings.ids)).gino.all():
            utils.files.safe_remove(get_image_local_path(product_id))
    await query.gino.status()
    return True


utils.routing.ModelView.register(
    router,
    "/",
    models.Product,
    schemes.Product,
    schemes.CreateProduct,
    custom_methods={"delete": delete_product, "batch_action": batch_product_action},
    request_handlers={
        "get": get_products,
        "get_one": get_product_noauth,
        "post": create_product,
        "patch": patch_product,
        "get_count": products_count,
    },
    scopes=["product_management"],
)
