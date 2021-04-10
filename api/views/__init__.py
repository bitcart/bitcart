from fastapi import APIRouter

from .configurator import router as configurator_router
from .cryptos import router as crypto_router
from .discounts import router as discount_router
from .invoices import router as invoice_router
from .manage import router as manage_router
from .notifications import router as notification_router
from .products import router as product_router
from .stores import router as store_router
from .templates import router as template_router
from .token import router as token_router
from .tor import router as tor_router
from .update import router as update_router
from .users import router as user_router
from .wallets import router as wallet_router
from .websocket import router as websocket_router

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
