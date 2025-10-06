from typing import Annotated, Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends, Request, Response, Security

from api import models, utils
from api.constants import AuthScopes
from api.schemas.invoices import CreateInvoice, CustomerUpdateData, DisplayInvoice, MethodUpdateData, UpdateInvoice
from api.schemas.refunds import DisplayRefund, RefundData, SubmitRefundData
from api.services.crud.invoices import InvoiceService
from api.services.crud.refunds import RefundService
from api.services.plugin_registry import PluginRegistry
from api.utils.routing import SearchPagination, create_crud_router, provide_pagination

router = APIRouter(route_class=DishkaRoute)


@router.get("/export")
async def export_invoices(
    pagination: Annotated[SearchPagination, Depends(provide_pagination)],
    invoice_service: FromDishka[InvoiceService],
    request: Request,
    response: Response,
    export_format: str = "json",
    add_payments: bool = False,
    all_users: bool = False,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.INVOICE_MANAGEMENT]),
) -> Any:
    return await invoice_service.export_invoices(pagination, request, response, export_format, add_payments, all_users, user)


create_crud_router(
    CreateInvoice,
    UpdateInvoice,
    DisplayInvoice,
    InvoiceService,
    router=router,
    required_scopes=[AuthScopes.INVOICE_MANAGEMENT],
    auth_config={"create": False, "get": False},
)


@router.post("/order_id/{order_id:path}", response_model=DisplayInvoice)
async def get_or_create_invoice_by_order_id(
    invoice_service: FromDishka[InvoiceService],
    order_id: str,
    data: CreateInvoice,
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.INVOICE_MANAGEMENT]),
) -> Any:
    return await invoice_service.get_or_create_invoice_by_order_id(order_id, data, user)


@router.patch("/{model_id}/customer", response_model=DisplayInvoice)
async def update_invoice(
    invoice_service: FromDishka[InvoiceService],
    plugin_registry: FromDishka[PluginRegistry],
    model_id: str,
    data: CustomerUpdateData,
) -> Any:
    item = await invoice_service.get(model_id)
    kwargs = {field: value for field, value in data if not getattr(item, field) and value}
    if kwargs:
        await plugin_registry.run_hook("invoice_customer_update", item, kwargs)
        item.update(**kwargs)
    return item


@router.patch("/{model_id}/details")
async def update_payment_details(
    invoice_service: FromDishka[InvoiceService],
    model_id: str,
    data: MethodUpdateData,
) -> Any:  # pragma: no cover
    return await invoice_service.update_payment_details(model_id, data)


@router.post("/{model_id}/refunds", response_model=DisplayRefund)
async def refund_invoice(
    refund_service: FromDishka[RefundService],
    data: RefundData,
    model_id: str,
    user: models.User = Security(
        utils.authorization.auth_dependency, scopes=[AuthScopes.INVOICE_MANAGEMENT, AuthScopes.PAYOUT_MANAGEMENT]
    ),
) -> Any:
    return await refund_service.create_refund(data, model_id, user)


@router.get("/refunds/{refund_id}", response_model=DisplayRefund)
async def get_refund(refund_service: FromDishka[RefundService], refund_id: str) -> Any:
    return await refund_service.get(refund_id)


@router.post("/refunds/{refund_id}/submit", response_model=DisplayRefund)
async def submit_refund(refund_service: FromDishka[RefundService], refund_id: str, data: SubmitRefundData) -> Any:
    return await refund_service.submit_refund(refund_id, data)
