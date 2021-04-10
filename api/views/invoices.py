from typing import List

from fastapi import APIRouter, HTTPException, Response, Security
from fastapi.responses import StreamingResponse

from .. import crud, models, schemes, utils
from ..ext import export as export_ext
from ..invoices import InvoiceStatus

router = APIRouter()


async def get_invoice_noauth(model_id: int):
    item = await models.Invoice.get(model_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with id {model_id} does not exist!")
    await crud.invoices.invoice_add_related(item)
    return item


@router.get("/order_id/{order_id}", response_model=schemes.DisplayInvoice)
async def get_invoice_by_order_id(order_id: str):
    item = await models.Invoice.query.where(models.Invoice.order_id == order_id).gino.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Object with order id {order_id} does not exist!")
    await crud.invoices.invoice_add_related(item)
    return item


@router.get("/export", response_model=List[schemes.DisplayInvoice])
async def export_invoices(
    response: Response,
    export_format: str = "json",
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["invoice_management"]),
):
    data = (
        await models.Invoice.query.where(models.User.id == user.id)
        .where(models.Invoice.status == InvoiceStatus.COMPLETE)
        .gino.all()
    )
    await crud.invoices.invoices_add_related(data)
    now = utils.time.now()
    filename = now.strftime(f"bitcartcc-export-%Y%m%d-%H%M%S.{export_format}")
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    response.headers.update(headers)
    if export_format == "json":
        return data
    else:
        return StreamingResponse(
            iter([export_ext.json_to_csv(export_ext.db_to_json(data)).getvalue()]),
            media_type="application/csv",
            headers=headers,
        )


utils.routing.ModelView.register(
    router,
    "/",
    models.Invoice,
    schemes.Invoice,
    schemes.CreateInvoice,
    schemes.DisplayInvoice,
    custom_methods={
        "get": crud.invoices.get_invoices,
        "get_one": crud.invoices.get_invoice,
        "post": crud.invoices.create_invoice,
        "delete": crud.invoices.delete_invoice,
        "batch_action": crud.invoices.batch_invoice_action,
    },
    request_handlers={"get_one": get_invoice_noauth},
    post_auth=False,
    scopes=["invoice_management"],
    custom_commands={"mark_complete": crud.invoices.mark_invoice_complete, "mark_invalid": crud.invoices.mark_invoice_invalid},
)
