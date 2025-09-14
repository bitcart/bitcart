from api.constants import AuthScopes
from api.schemas.discounts import CreateDiscount, DisplayDiscount, UpdateDiscount
from api.services.crud.discounts import DiscountService
from api.utils.routing import create_crud_router

router = create_crud_router(
    CreateDiscount,
    UpdateDiscount,
    DisplayDiscount,
    DiscountService,
    required_scopes=[AuthScopes.DISCOUNT_MANAGEMENT],
)
