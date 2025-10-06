from decimal import Decimal
from typing import Annotated, Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Security, UploadFile

from api import models, utils
from api.constants import AuthScopes
from api.schemas.base import DecimalAsFloat
from api.schemas.products import CreateProduct, DisplayProduct, OptionalProductSchema, UpdateProduct
from api.services.crud.products import ProductService
from api.utils.routing import (
    OffsetPagination,
    SearchPagination,
    create_crud_router,
    provide_pagination,
)

router = APIRouter(route_class=DishkaRoute)


@router.get("/categories", response_model=list[str])
async def categories(product_service: FromDishka[ProductService], store: str) -> Any:
    return await product_service.get_all_categories(store)


@router.get("/maxprice", response_model=DecimalAsFloat)
async def get_max_product_price(product_service: FromDishka[ProductService], store: str) -> Any:
    return await product_service.get_max_product_price(store)


create_crud_router(
    CreateProduct,
    UpdateProduct,
    DisplayProduct,
    ProductService,
    router=router,
    disabled_endpoints={"create": True, "update": True, "list": True, "count": True, "get": True},
    required_scopes=[AuthScopes.PRODUCT_MANAGEMENT],
)


@router.post("", response_model=DisplayProduct)
async def create_product_multipart(
    product_service: FromDishka[ProductService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.PRODUCT_MANAGEMENT]),
    data: str = Form(..., description="JSON string containing product data"),
    image: UploadFile = File(None, description="Product image"),
) -> Any:
    parsed_data = utils.files.parse_data(data, CreateProduct)
    return await product_service.create_with_image(parsed_data, user, image)


@router.patch("/{item_id}", response_model=DisplayProduct)
async def update_product_multipart(
    item_id: str,
    product_service: FromDishka[ProductService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.PRODUCT_MANAGEMENT]),
    data: str = Form(..., description="JSON string containing product update data"),
    image: UploadFile = File(None, description="Product image"),
) -> Any:
    parsed_data = utils.files.parse_data(data, OptionalProductSchema)
    return await product_service.update_with_image(parsed_data, item_id, user, image)


@router.get("", response_model=OffsetPagination[DisplayProduct])
async def list_items(
    pagination: Annotated[SearchPagination, Depends(provide_pagination)],
    product_service: FromDishka[ProductService],
    request: Request,
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.PRODUCT_MANAGEMENT]),
    store: str | None = None,
    category: str | None = "",
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sale: bool | None = False,
) -> Any:
    if not user and store is None:
        raise HTTPException(401, "Unauthorized")
    statement, filters = product_service._filter_in_product(store, category, min_price, max_price, sale)
    return await product_service.paginate(request, pagination, user=user, statement=statement, filters=filters)


@router.get("/count", response_model=int)
async def products_count(
    pagination: Annotated[SearchPagination, Depends(provide_pagination)],
    product_service: FromDishka[ProductService],
    request: Request,
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.PRODUCT_MANAGEMENT]),
    store: str | None = None,
    category: str | None = "",
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sale: bool | None = False,
) -> Any:
    if store is None and not user:
        raise HTTPException(401, "Unauthorized")
    statement, filters = product_service._filter_in_product(store, category, min_price, max_price, sale)
    _, count = await product_service.paginated_list_and_count(
        request, pagination, user=user, statement=statement, filters=filters, count_only=True
    )
    return count


@router.get("/{model_id}", response_model=DisplayProduct)
async def get_product(product_service: FromDishka[ProductService], model_id: str, store: str | None = None) -> Any:
    return await product_service.get(model_id, store_id=store)
