from fastapi import APIRouter

from api import crud, models, schemes, utils

router = APIRouter(tags=["payouts"])


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.Payout,
    schemes.UpdatePayout,
    schemes.CreatePayout,
    schemes.DisplayPayout,
    custom_methods={
        "post": crud.payouts.create_payout,
        "batch_action": crud.payouts.batch_payout_action,
    },
    scopes=["payout_management"],
    custom_commands={
        "approve": crud.payouts.approve_payouts,
        "send": crud.payouts.send_payouts,
        "cancel": crud.payouts.cancel_payouts,
    },
)
