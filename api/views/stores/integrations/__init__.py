from fastapi import APIRouter

from api.views.stores.integrations.shopify import router as shopify_router

router = APIRouter()

router.include_router(shopify_router, prefix="/shopify")
