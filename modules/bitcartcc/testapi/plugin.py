from api import models
from api.plugins import BasePlugin, publish_event, register_event, register_event_handler, register_hook, update_metadata

from .views import router


class Plugin(BasePlugin):
    name = "testapi"

    def setup_app(self, app):
        app.include_router(router)

    async def startup(self):
        register_hook("invoice_created", self.handle_invoice)
        self.register_template("test", applicable_to="product")
        register_event("test_event", ["message"])
        register_event_handler("test_event", self.handle_event)
        register_event_handler("invoice_status", self.handle_event)

    async def shutdown(self):
        pass

    async def worker_setup(self):
        pass

    async def handle_invoice(self, invoice):
        print("Invoice created", invoice)
        await publish_event("test_event", {"message": "Hello world!"})
        return await update_metadata(models.Invoice, invoice.id, "rating", 0)

    async def handle_event(self, event, event_data):
        print("Event received", event, event_data)
