from api.plugins import BasePlugin, register_hook

from .views import router


class Plugin(BasePlugin):
    name = "testapi"

    def setup_app(self, app):
        app.include_router(router)

    async def startup(self):
        register_hook("invoice_created", self.handle_invoice)

    async def shutdown(self):
        pass

    async def handle_invoice(self, invoice):
        print("Invoice created", invoice)
