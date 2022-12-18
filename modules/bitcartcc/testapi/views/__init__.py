from fastapi import APIRouter

from api import utils

from .. import models, schemes

router = APIRouter()


@router.get("/testpage")
async def testpage():
    return {"testpage": "testpage"}


utils.routing.ModelView.register(
    router,
    "/reviews",
    models.Reviews,
    schemes.Review,
    schemes.CreateReview,
    scopes=["reviews_management"],
    using_router=False,
)
