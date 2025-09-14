from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from api.views.configurator import router as configurator_router
from api.views.cryptos import router as cryptos_router
from api.views.discounts import router as discounts_router
from api.views.files import router as files_router
from api.views.invoices import router as invoices_router
from api.views.manage import router as manage_router
from api.views.notifications import router as notifications_router
from api.views.payouts import router as payouts_router
from api.views.plugins import router as plugins_router
from api.views.products import router as products_router
from api.views.stores import router as stores_router
from api.views.templates import router as templates_router
from api.views.token import router as token_router
from api.views.tor import router as tor_router
from api.views.update import router as update_router
from api.views.users import router as users_router
from api.views.wallets import router as wallets_router
from api.views.websocket import router as websocket_router

router = APIRouter(route_class=DishkaRoute)


router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
router.include_router(templates_router, prefix="/templates", tags=["templates"])
router.include_router(stores_router, prefix="/stores", tags=["stores"])
router.include_router(discounts_router, prefix="/discounts", tags=["discounts"])
router.include_router(products_router, prefix="/products", tags=["products"])
router.include_router(invoices_router, prefix="/invoices", tags=["invoices"])
router.include_router(payouts_router, prefix="/payouts", tags=["payouts"])

router.include_router(manage_router, prefix="/manage", tags=["manage"])
router.include_router(tor_router, prefix="/tor", tags=["tor"])
router.include_router(update_router, prefix="/update", tags=["update"])
router.include_router(cryptos_router, prefix="/cryptos", tags=["cryptos"])
router.include_router(files_router, prefix="/files", tags=["files"])
router.include_router(configurator_router, prefix="/configurator", tags=["configurator"])
router.include_router(plugins_router, prefix="/plugins", tags=["plugins"])

router.include_router(token_router, prefix="/token", tags=["token"])
router.include_router(websocket_router, prefix="/ws", tags=["websocket"])
