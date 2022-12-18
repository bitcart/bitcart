from api import models
from api.plugins import BasePlugin, register_hook, update_metadata

from .views import router


class Plugin(BasePlugin):
    name = "testapi"

    def setup_app(self, app):
        app.include_router(router)

    async def startup(self):
        register_hook("invoice_created", self.handle_invoice)

    async def shutdown(self):
        pass

    async def worker_setup(self):
        pass

    async def handle_invoice(self, invoice):
        print("Invoice created", invoice)
        return await update_metadata(models.Invoice, invoice.id, "rating", 0)
