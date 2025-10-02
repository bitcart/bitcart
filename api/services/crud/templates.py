from typing import Any

from dishka import AsyncContainer
from sqlalchemy import select

from api import exceptions, models, templates, utils
from api.db import AsyncSession
from api.logging import get_logger
from api.schemas.policies import Policy
from api.services.crud import CRUDService
from api.services.crud.repositories import TemplateRepository
from api.services.settings import SettingService

logger = get_logger(__name__)


class TemplateService(CRUDService[models.Template]):
    repository_type = TemplateRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        template_manager: templates.TemplateManager,
        setting_service: SettingService,
    ) -> None:
        super().__init__(session, container)
        self.template_manager = template_manager
        self.setting_service = setting_service

    @staticmethod
    def get_template_matching_str(name: str, obj: models.Template | None = None) -> str:
        template_str = f'Template matching "{name}"'
        if obj and hasattr(obj, "id"):
            template_str += f" for {utils.common.get_object_name(obj)} {obj.id}"
        template_str += ":"
        return template_str

    async def get_global_template(self, name: str) -> templates.Template:  # pragma: no cover
        policy = await self.setting_service.get_setting(Policy)
        template_id = policy.global_templates.get(name)
        if template_id:
            custom_template = await self.get_or_none(template_id)
            if custom_template:
                logger.info(f'{self.get_template_matching_str(name, None)} selected global template "{custom_template.name}"')
                return templates.Template(name, custom_template.text)
        if name in self.template_manager.templates:
            logger.info(f"{self.get_template_matching_str(name, None)} selected default template")
            return self.template_manager.templates[name]
        raise exceptions.TemplateDoesNotExistError(f"Template {name} does not exist and has no default")

    async def get_template(self, name: str, user_id: str | None = None, obj: Any = None) -> templates.Template:
        query = select(models.Template)
        if obj and obj.templates.get(name):
            query = query.where(models.Template.id == obj.templates[name])
        else:
            query = query.where(models.Template.name == name)
        if user_id:
            query = query.where(models.Template.user_id == user_id)
        custom_template = await self.get_or_none(None, statement=query)
        if custom_template:
            logger.info(f'{self.get_template_matching_str(name, obj)} selected custom template "{custom_template.name}"')
            return templates.Template(name, custom_template.text)
        if name in self.template_manager.templates:
            logger.info(f"{self.get_template_matching_str(name, obj)} selected default template")
            return self.template_manager.templates[name]
        raise exceptions.TemplateDoesNotExistError(f"Template {name} does not exist and has no default")

    async def get_product_template(self, store: models.Store, product: models.Product, quantity: int) -> str:
        template = await self.get_template("product", store.user_id, product)
        return template.render(store=store, product=product, quantity=quantity)

    async def get_store_template(self, store: models.Store, products: list[str]) -> str:
        template = await self.get_template("shop", store.user_id, store)
        return template.render(store=store, products=products)

    async def get_notify_template(self, store: models.Store, invoice: models.Invoice) -> str:
        template = await self.get_template("notification", store.user_id, store)
        return template.render(store=store, invoice=invoice)

    async def get_customer_refund_template(
        self, store: models.Store, invoice: models.Invoice, refund: models.Refund, refund_url: str
    ) -> str:  # pragma: no cover: patched in tests
        template = await self.get_template("customer_refund", store.user_id, store)
        return template.render(store=store, invoice=invoice, refund=refund, refund_url=refund_url)

    async def get_merchant_refund_notify_template(
        self, store: models.Store, invoice: models.Invoice, refund: models.Refund
    ) -> str:
        template = await self.get_template("merchant_refund_notify", store.user_id, store)
        return template.render(store=store, invoice=invoice, refund=refund)

    async def get_syncinfo_template(self, syncinfo_data: list[dict[str, Any]], failed_daemons: list[dict[str, Any]]) -> str:
        template = await self.get_global_template("syncinfo")
        return template.render(syncinfo_data=syncinfo_data, failed_daemons=failed_daemons)
