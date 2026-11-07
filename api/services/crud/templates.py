from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from dishka import AsyncContainer
from fastapi import HTTPException

from api import constants, exceptions, metrics, models, utils
from api.constants import LIGHTNING_DESCRIPTION_RENDER_TIMEOUT, MAX_LIGHTNING_DESCRIPTION_BYTES
from api.db import AsyncSession
from api.ext.moneyformat import currency_table
from api.logging import get_exception_message, get_logger
from api.plugins import delete_metadata, update_metadata
from api.redis import Redis
from api.schemas.policies import Policy
from api.schemas.tasks import SendTemplateAlertMessage
from api.schemas.templates import TemplateTestRequest, TemplateTestResult
from api.services.crud import CRUDAction, CRUDService
from api.services.crud.products import ProductService
from api.services.crud.repositories import TemplateRepository
from api.services.crud.stores import StoreService
from api.services.renderer import RendererClient, RendererReply, RenderFailure, RenderFailureKind
from api.services.settings import SettingService
from api.settings import Settings
from api.templates import RenderResult, Template, TemplateAudience, TemplateFormat, TemplateManager, TemplateScope
from api.templates.context import (
    ContextBuilder,
    TemplateOwner,
    TemplateTestData,
    describe_context,
    with_fields,
)
from api.types import TasksBroker

logger = get_logger(__name__)

RENDERER_ALERT_NAME = "renderer"
TEMPLATE_OWNERS: dict[TemplateScope, type[StoreService] | type[ProductService]] = {
    TemplateScope.STORE: StoreService,
    TemplateScope.PRODUCT: ProductService,
}


def source_line(text: str, line: int | None) -> str | None:
    if line is None:
        return None
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return None
    return lines[line - 1].strip()[: constants.TEMPLATE_MAX_SOURCE_LINE_LENGTH]


class TemplateService(CRUDService[models.Template]):
    repository_type = TemplateRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        template_manager: TemplateManager,
        setting_service: SettingService,
        renderer: RendererClient,
        redis_pool: Redis,
        broker: TasksBroker,
        settings: Settings,
    ) -> None:
        super().__init__(session, container)
        self.template_manager = template_manager
        self.setting_service = setting_service
        self.renderer = renderer
        self.redis_pool = redis_pool
        self.broker = broker
        self.settings = settings

    async def validate(
        self, action: CRUDAction, data: dict[str, Any], model: models.Template, user: models.User | None = None
    ) -> None:
        await super().validate(action, data, model, user)
        if data.get("text"):
            await self.ensure_compiles(data["text"])

    async def ensure_compiles(self, text: str) -> None:
        reply = await self.renderer.check(text)
        if not reply.ok:
            raise HTTPException(422, self._describe_error(reply.failure))

    @staticmethod
    def _describe_error(failure: RenderFailure) -> str:
        return f"Line {failure.line}: {failure.message}" if failure.line else failure.message

    def _definition(self, name: str) -> Template:
        definition = self.template_manager.templates.get(name)
        if definition is None:
            raise exceptions.TemplateDoesNotExistError(f"Template {name} does not exist and has no default")
        return definition

    @staticmethod
    def _subject_label(subject: TemplateOwner | None) -> str:
        return f" for {utils.common.get_object_name(subject)} {subject.id}" if subject is not None else ""

    async def _select_custom(self, definition: Template, owner: TemplateOwner | None) -> models.Template | None:
        if definition.applicable_to == TemplateScope.GLOBAL:
            policy = await self.setting_service.get_setting(Policy)
            template_id = policy.global_templates.get(definition.name)
            return await self.get_or_none(template_id) if template_id else None
        if owner is None:
            raise ValueError(f"Template {definition.name} needs an owner")
        selected = owner.templates.get(definition.name)
        if selected:
            return await self.get_or_none(selected, user_id=owner.user_id)
        return await self.get_or_none(None, name=definition.name, user_id=owner.user_id)

    async def render(
        self,
        name: str,
        /,
        *,
        owner: TemplateOwner | None = None,
        renderer_timeout: float | None = None,
        **context: Any,
    ) -> RenderResult:
        definition = self._definition(name)
        custom = await self._select_custom(definition, owner)
        selected = f'custom template "{custom.name}"' if custom is not None else "default template"
        logger.info(f'Template matching "{name}"{self._subject_label(owner)}: selected {selected}')
        try:
            if custom is None:
                return self._accept(*await self._render_default(definition, context, renderer_timeout))
            is_html = custom.format == TemplateFormat.HTML
            reply, builder = await self._render_text(custom.text, context, html=is_html, max_wait=renderer_timeout)
            if reply.ok:
                result = self._accept(reply, builder)
                if not result.text.strip():
                    label = self._subject_label(owner)
                    logger.warning(f'Template "{custom.name}" used as {definition.name} rendered empty text{label}')
                return result
            report = self._report_failure(definition, custom, owner, reply, context)
            fallback = self._accept(*await self._render_default(definition, context, renderer_timeout))
        except exceptions.RendererUnavailableError as e:
            await self._report_unavailable(definition.name, e)
            raise
        if definition.audience == TemplateAudience.AUTHOR:
            return fallback.with_note(RenderResult(report))
        await self._send_alert(self._alert_store_id(owner), definition.name, report)
        return replace(fallback, is_fallback=True)

    async def _render_text(
        self, text: str, context: Mapping[str, Any], *, html: bool = False, max_wait: float | None = None
    ) -> tuple[RendererReply, ContextBuilder]:
        builder = ContextBuilder(html=html)
        view = builder.build(context)
        return await self.renderer.render(text, view, autoescape=html, safe_key=builder.safe_key, max_wait=max_wait), builder

    async def _render_default(
        self, definition: Template, context: Mapping[str, Any], renderer_timeout: float | None = None
    ) -> tuple[RendererReply, ContextBuilder]:
        reply, builder = await self._render_text(definition.text, context, max_wait=renderer_timeout)
        if reply.ok:
            return reply, builder
        failure = reply.failure
        if failure.kind.is_environment:
            raise exceptions.RendererUnavailableError(f"default template {definition.name}: {failure.message}")
        raise exceptions.TemplateRenderError(f"Default template {definition.name} failed: {self._describe_error(failure)}")

    def _accept(self, reply: RendererReply, builder: ContextBuilder) -> RenderResult:
        self._apply_writes(reply, builder)
        return builder.finish(reply.text)

    @staticmethod
    def _apply_writes(reply: RendererReply, builder: ContextBuilder) -> None:
        for write in reply.writes:
            target = builder.targets.get(write.ref)
            if target is None:
                continue
            if write.op == "set":
                update_metadata(target, write.key, write.value)
            else:
                delete_metadata(target, write.key)

    def _report_failure(
        self,
        definition: Template,
        custom: models.Template,
        owner: TemplateOwner | None,
        reply: RendererReply,
        context: Mapping[str, Any],
    ) -> str:
        failure = reply.failure
        metrics.template_render_failures_total.labels(template=definition.name, kind=failure.kind).inc()
        lines = [f'Template "{definition.name}" (your template "{custom.name}") failed{self._subject_label(owner)}']
        if (line := source_line(custom.text, failure.line)) is not None:
            lines.append(f"Line {failure.line}: {line}")
        lines.append(f"Error: {failure.message}")
        lines.append(f"Data: {describe_context(context)}")
        lines.append("The default template was used instead.")
        report = "\n".join(lines)
        logger.error(report)
        return report

    async def _report_unavailable(self, name: str, error: Exception) -> None:
        metrics.template_render_failures_total.labels(template=name, kind=RenderFailureKind.UNAVAILABLE).inc()
        message = f'Template "{name}" could not be rendered: {get_exception_message(error)}'
        logger.error(message)
        await self._send_alert(None, RENDERER_ALERT_NAME, message)

    @staticmethod
    def _alert_store_id(owner: TemplateOwner | None) -> str | None:
        if isinstance(owner, models.Store):
            return owner.id
        if isinstance(owner, models.Product):
            return owner.store_id
        return None

    async def _send_alert(self, store_id: str | None, name: str, text: str) -> None:
        try:
            scope = store_id if store_id is not None else "global"
            if not await self.redis_pool.set(f"template_alert:{scope}:{name}", 1, ex=constants.TEMPLATE_ALERT_WINDOW, nx=True):
                return
            await self.broker.publish(
                "send_template_alert",
                SendTemplateAlertMessage(store_id=store_id, text=text),
            )
        except Exception as e:
            logger.error(f"Failed to queue template alert for {name}: {get_exception_message(e)}")

    async def with_fallback_note(self, message: RenderResult, store: models.Store, invoice: models.Invoice) -> RenderResult:
        if not message.is_fallback:
            return message
        return message.with_note(await self.render("fallback_note", owner=store, store=store, invoice=invoice))

    @staticmethod
    def _product_context(invoice: models.Invoice, relation: models.ProductxInvoice) -> dict[str, Any]:
        product = relation.product
        price = currency_table.round_neutral(invoice.currency, product.price)
        return {"product": with_fields(product, price=price), "quantity": relation.count}

    async def render_product(
        self, store: models.Store, invoice: models.Invoice, relation: models.ProductxInvoice
    ) -> RenderResult:
        return await self.render("product", owner=relation.product, store=store, **self._product_context(invoice, relation))

    async def preview_product(
        self, store: models.Store, invoice: models.Invoice, relation: models.ProductxInvoice
    ) -> RenderResult:
        context = {"store": store, **self._product_context(invoice, relation)}
        reply, builder = await self._render_default(self._definition("product"), context)
        return builder.finish(reply.text)

    async def render_order_email(self, store: models.Store, invoice: models.Invoice) -> RenderResult:
        parts = [await self.render_product(store, invoice, relation) for relation in invoice.products_associations]
        message = await self.render("shop", owner=store, store=store, products=parts)
        return await self.with_fallback_note(message, store, invoice)

    async def render_notification(self, store: models.Store, invoice: models.Invoice) -> RenderResult:
        return await self.render("notification", owner=store, store=store, invoice=invoice)

    async def render_lightning_description(
        self, store: models.Store, invoice: models.Invoice, product: models.Product | None
    ) -> str:
        try:
            result = await self.render(
                "lightning_description",
                owner=store,
                store=store,
                renderer_timeout=LIGHTNING_DESCRIPTION_RENDER_TIMEOUT,
                invoice=invoice,
                product=product,
            )
        except exceptions.RendererUnavailableError:
            return ""
        return result.text.encode()[:MAX_LIGHTNING_DESCRIPTION_BYTES].decode(errors="ignore")

    async def render_customer_refund(
        self, store: models.Store, invoice: models.Invoice, refund: models.Refund, refund_url: str
    ) -> RenderResult:
        message = await self.render(
            "customer_refund", owner=store, store=store, invoice=invoice, refund=refund, refund_url=refund_url
        )
        return await self.with_fallback_note(message, store, invoice)

    async def render_merchant_refund_notify(
        self, store: models.Store, invoice: models.Invoice, refund: models.Refund
    ) -> RenderResult:
        return await self.render("merchant_refund_notify", owner=store, store=store, invoice=invoice, refund=refund)

    async def render_syncinfo(self, syncinfo_data: list[dict[str, Any]], failed_daemons: list[dict[str, Any]]) -> RenderResult:
        return await self.render("syncinfo", syncinfo_data=syncinfo_data, failed_daemons=failed_daemons)

    async def test_template(self, template_id: str, data: TemplateTestRequest, user: models.User) -> TemplateTestResult:
        template = await self.get(template_id, user)
        name = data.name or template.name
        definition = self.template_manager.templates.get(name)
        if definition is None:
            raise HTTPException(422, f"Choose which template to test this as: {name} is not a known template")
        if definition.applicable_to == TemplateScope.GLOBAL and not user.is_superuser:
            raise HTTPException(403, "Only superusers can test global templates")
        await self._check_test_rate_limit(user)
        owner = await self._test_owner(definition, data.owner_id, user)
        context = await definition.get_test_context(TemplateTestData(owner=owner, user=user, container=self.container))
        reply, builder = await self._render_text(template.text, context, html=template.format == TemplateFormat.HTML)
        if reply.ok:
            result = builder.finish(reply.text)
            return TemplateTestResult(ok=True, text=result.text, is_html=result.is_html)
        failure = reply.failure
        return TemplateTestResult(
            ok=False,
            line=failure.line,
            source_line=source_line(template.text, failure.line),
            error=failure.message,
        )

    async def _test_owner(self, definition: Template, owner_id: str | None, user: models.User) -> TemplateOwner | None:
        service_type = TEMPLATE_OWNERS.get(definition.applicable_to)
        if owner_id is None or service_type is None:
            return None
        service = await self.container.get(service_type)
        return await service.get(owner_id, None if user.is_superuser else user)

    async def _check_test_rate_limit(self, user: models.User) -> None:
        if self.settings.is_testing():
            return
        await utils.redis.check_rate_limit(
            self.redis_pool,
            f"template_test:rate:{user.id}",
            constants.TEMPLATE_TEST_MAX_ATTEMPTS,
            constants.TEMPLATE_TEST_RATE_WINDOW,
            "Too many template tests. Please try again later.",
        )
