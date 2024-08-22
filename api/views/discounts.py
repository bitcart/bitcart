from fastapi import APIRouter

from api import models, schemes, utils

router = APIRouter()

crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.Discount,
    schemes.UpdateDiscount,
    schemes.CreateDiscount,
    schemes.DisplayDiscount,
    scopes=["discount_management"],
)
