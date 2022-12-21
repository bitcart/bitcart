from fastapi import APIRouter

from api.views.configurator import router as configurator_router
from api.views.cryptos import router as crypto_router
from api.views.discounts import router as discount_router
from api.views.invoices import router as invoice_router
from api.views.manage import router as manage_router
from api.views.notifications import router as notification_router
from api.views.payouts import router as payout_router
from api.views.plugins import router as plugin_router
from api.views.products import router as product_router
from api.views.stores import router as store_router
from api.views.templates import router as template_router
from api.views.token import router as token_router
from api.views.tor import router as tor_router
from api.views.update import router as update_router
from api.views.users import router as user_router
from api.views.wallets import router as wallet_router
from api.views.websocket import router as websocket_router

router = APIRouter()

# We separate views by object type

# Websocket routes
router.include_router(websocket_router, prefix="/ws")

# Regular routes
router.include_router(user_router, prefix="/users")
router.include_router(wallet_router, prefix="/wallets")
router.include_router(store_router, prefix="/stores")
router.include_router(discount_router, prefix="/discounts")
router.include_router(notification_router, prefix="/notifications")
router.include_router(template_router, prefix="/templates")
router.include_router(product_router, prefix="/products")
router.include_router(invoice_router, prefix="/invoices")
router.include_router(payout_router, prefix="/payouts")


# Authorization
router.include_router(token_router, prefix="/token")

# Maintenance
router.include_router(manage_router, prefix="/manage")

# Cryptocurrency-related views
router.include_router(crypto_router, prefix="/cryptos")

# Extensions
router.include_router(configurator_router, prefix="/configurator")
router.include_router(tor_router, prefix="/tor")
router.include_router(update_router, prefix="/update")

router.include_router(plugin_router, prefix="/plugins")
