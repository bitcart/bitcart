from api.constants import AuthScopes
from api.schemas.payouts import CreatePayout, DisplayPayout, UpdatePayout
from api.services.crud.payouts import PayoutService
from api.utils.routing import create_crud_router

router = create_crud_router(
    CreatePayout,
    UpdatePayout,
    DisplayPayout,
    PayoutService,
    required_scopes=[AuthScopes.PAYOUT_MANAGEMENT],
)
