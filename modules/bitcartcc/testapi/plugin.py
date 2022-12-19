from api import models
from api.plugins import (
    BasePlugin,
    publish_event,
    register_event,
    register_event_handler,
    register_filter,
    register_hook,
    update_metadata,
)

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
        register_hook("pre_deploy", self.pre_deploy)
        register_hook("post_deploy", self.post_deploy)
        register_filter("search_filters", self.add_search_filters)

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

    async def pre_deploy(self, task_id, task):
        print("Pre deploy", task_id, task)

    async def post_deploy(self, task_id, task, success, output):
        print("Post deploy", task_id, task, success, output)

    async def add_search_filters(self, query, model, *args, **kwargs):
        for name, value in kwargs.items():
            if hasattr(model, name):
                query = query.where(getattr(model, name) == value)
        return query
