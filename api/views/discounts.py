from fastapi import APIRouter

from api import crud, models, schemes, utils

router = APIRouter()

utils.routing.ModelView.register(
    router,
    "/",
    models.Discount,
    schemes.Discount,
    schemes.CreateDiscount,
    custom_methods={"post": crud.discounts.create_discount},
    scopes=["discount_management"],
)
