import asyncio
import json
import logging
import pathlib
import re
import struct
import tempfile
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
import pytest_mock
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from httpx import AsyncClient as TestClient
from pydantic_core import PydanticSerializationError
from sqlalchemy import func, select

from api import exceptions, models, templates
from api.constants import LIGHTNING_DESCRIPTION_RENDER_TIMEOUT
from api.invoices import InvoiceStatus
from api.redis import Redis
from api.schemas.misc import EmailSettings
from api.schemas.stores import StoreCheckoutSettings, StorePluginSettings
from api.services.crud.invoices import InvoiceService
from api.services.crud.products import ProductService
from api.services.crud.stores import StoreService
from api.services.crud.templates import TEMPLATE_OWNERS, TemplateService
from api.services.renderer import MAX_REPLY_BYTES, MAX_REQUEST_BYTES, RendererClient, RendererReply, RenderFailureKind
from api.settings import Settings
from api.templates import RenderResult, TemplateAudience, TemplateManager, TemplateScope
from api.templates.context import (
    ContextBuilder,
    TemplateTestData,
    sample_model,
)
from api.templates.defaults import default_templates
from tests.helper import create_invoice, create_product, create_store, create_token, create_user

pytestmark = pytest.mark.anyio


@pytest.fixture
def renderer(settings: Settings) -> RendererClient:
    return RendererClient(settings)


@pytest.fixture
async def container(app: FastAPI) -> AsyncIterator[AsyncContainer]:
    async with app.state.dishka_container(scope=Scope.REQUEST) as request_container:
        yield request_container


@pytest.fixture
async def service(container: AsyncContainer, mocker: pytest_mock.MockerFixture) -> TemplateService:
    template_service = await container.get(TemplateService)
    mocker.patch.object(template_service.broker, "publish", new=AsyncMock())
    return template_service


def alerts(service: TemplateService) -> list[Any]:
    return [call.args[1] for call in service.broker.publish.call_args_list if call.args[0] == "send_template_alert"]  # type: ignore[attr-defined]


async def save_template(client: TestClient, token: str, name: str, text: str, **attrs: Any) -> dict[str, Any]:
    resp = await client.post(
        "/templates", json={"name": name, "text": text, **attrs}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def load_store(container: AsyncContainer, store_id: str) -> models.Store:
    return await (await container.get(StoreService)).get(store_id)


def sample_store() -> models.Store:
    store = models.Store(id="store1", name="Joe", default_currency="USD", user_id="owner", meta={"keep": 1})
    store.checkout_settings = StoreCheckoutSettings()
    store.plugin_settings = StorePluginSettings()
    store.email_settings = EmailSettings()
    return store


async def empty_test_context(data: TemplateTestData[Any]) -> dict[str, Any]:
    return {}


async def render_view(renderer: RendererClient, text: str, **context: Any) -> Any:
    return await renderer.render(text, ContextBuilder().build(context))


TEMPLATE_MODELS = [model for model in models.all_tables.values() if not model.template_blocked]
BLOCKED_MODELS = [models.User, models.Wallet, models.Notification, models.Token, models.Setting]
SECRET_NAME = re.compile("password|secret|token|api_key|private|xpub|seed|mnemonic", re.IGNORECASE)


def view_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from view_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from view_keys(item)


@pytest.mark.parametrize("model", TEMPLATE_MODELS, ids=lambda model: model.__name__)
def test_no_visible_field_is_named_like_a_secret(model: type[models.Model]) -> None:
    view = ContextBuilder().build({"item": sample_model(model)})
    assert [key for key in view_keys(view) if SECRET_NAME.search(key)] == []


@pytest.mark.parametrize("model", BLOCKED_MODELS, ids=lambda model: model.__name__)
def test_blocked_models_are_refused_by_name(model: type[models.Model]) -> None:
    with pytest.raises(TypeError, match=model.__name__):
        ContextBuilder().build({"item": model()})


def test_only_exposed_relations_are_followed() -> None:
    invoice = ContextBuilder().build({"invoice": sample_model(models.Invoice)})["invoice"]
    assert {"payments", "refunds", "products_associations"} <= set(invoice)
    assert "store" not in invoice
    assert "invoice" not in invoice["payments"][0]
    assert "invoice" not in invoice["refunds"][0]
    association = invoice["products_associations"][0]
    assert "invoice" not in association
    assert not {"store", "discounts", "user"} & set(association["product"])


async def test_unloaded_relations_are_skipped_in_computed_fields(
    client: TestClient, token: str, container: AsyncContainer
) -> None:
    invoice_id = (await create_invoice(client, token))["id"]
    invoices = await container.get(InvoiceService)
    invoices.session.add(models.Refund(amount=Decimal(3), currency="USD", invoice_id=invoice_id))
    await invoices.session.commit()
    view = ContextBuilder().build({"invoice": await invoices.get(invoice_id)})["invoice"]
    refund = view["refunds"][0]
    assert refund["amount"] == {"$decimal": "3.000000000000000000"}
    assert "payout_status" not in refund


def test_other_property_errors_are_not_hidden(mocker: pytest_mock.MockerFixture) -> None:
    refund = models.Refund(id="1", amount=Decimal(1), currency="USD")
    mocker.patch.object(models.Refund, "payout_status", property(mocker.Mock(side_effect=AttributeError("bug"))))
    with pytest.raises(AttributeError, match="bug"):
        ContextBuilder().build({"refund": refund})


def test_unknown_template_file_raises() -> None:
    with pytest.raises(exceptions.TemplateLoadError):
        templates.Template(
            "missing", applicable_to=TemplateScope.STORE, audience=TemplateAudience.AUTHOR, get_test_context=empty_test_context
        )


@pytest.mark.parametrize("definition", default_templates(), ids=lambda definition: definition.name)
async def test_every_default_renders_its_test_data(client: TestClient, token: str, definition: templates.Template) -> None:
    template = await save_template(client, token, f"copy of {definition.name}", definition.text)
    body = (await run_test(client, token, template["id"], name=definition.name)).json()
    assert body["ok"], body
    assert body["text"].strip()


def test_every_owning_scope_has_a_service() -> None:
    assert set(TEMPLATE_OWNERS) == set(TemplateScope) - {TemplateScope.GLOBAL}


@pytest.mark.parametrize(("currency", "price", "expected"), [("USD", "10.5", "10.50"), ("BTC", "0.00000001", "0.00000001")])
async def test_format_decimal(renderer: RendererClient, currency: str, price: str, expected: str) -> None:
    invoice = {"currency": currency, "price": Decimal(price)}
    assert (await render_view(renderer, '{{ invoice | format_decimal("price") }}', invoice=invoice)).text == expected


async def test_decimals_stay_exact(renderer: RendererClient) -> None:
    price = Decimal("21.000000000000000000")
    reply = await render_view(renderer, "{{ price * 2 }}|{{ price > 100 }}|{{ 100 > price }}|{{ price == 21 }}", price=price)
    assert reply.text == "42.000000000000000000|False|True|True"


def test_context_is_plain_data_without_hidden_fields() -> None:
    view = ContextBuilder().build({"store": sample_store()})["store"]
    assert view["name"] == "Joe"
    assert view["meta"] == {"keep": 1}
    assert not {"email_settings", "plugin_settings", "wallets", "notifications", "user"} & set(view)
    json.dumps(view)


async def test_templates_have_no_object_methods(renderer: RendererClient) -> None:
    store = sample_store()
    assert (await render_view(renderer, "{% if store.update %}method{% else %}none{% endif %}", store=store)).text == "none"
    assert store.user_id == "owner"


def test_unknown_objects_are_refused() -> None:
    with pytest.raises(PydanticSerializationError):
        ContextBuilder().build({"anything": object()})


def test_datetimes_keep_their_text_format_and_other_types_are_serialized() -> None:
    moment = datetime(2026, 11, 7, 12, 30, tzinfo=UTC)
    identifier = UUID("12345678-1234-5678-1234-567812345678")
    view = ContextBuilder().build({"moment": moment, "day": date(2026, 11, 7), "identifier": identifier})
    assert view == {"moment": "2026-11-07 12:30:00+00:00", "day": "2026-11-07", "identifier": str(identifier)}


async def test_oversized_context_is_not_sent(renderer: RendererClient) -> None:
    reply = await renderer.render("x", {"data": "x" * MAX_REQUEST_BYTES})
    assert not reply.ok
    assert reply.error is not None
    assert reply.error.kind == RenderFailureKind.CONTEXT


@pytest.mark.parametrize(
    ("text", "context", "kind"),
    [
        ("{% if %}", {}, RenderFailureKind.SYNTAX),
        ("{{ 1 / 0 }}", {}, RenderFailureKind.RUNTIME),
        ("{{ 'x' * 2000000 }}", {}, RenderFailureKind.OUTPUT),
        ("{{ 'x' * 20000000 }}", {}, RenderFailureKind.MEMORY),
        (
            "{% for i in range(100000) %}{% set product = big * big %}{% endfor %}",
            {"big": {"$decimal": "9" * 4000}},
            RenderFailureKind.TIMEOUT,
        ),
    ],
)
async def test_renderer_failure_kinds_are_understood(
    renderer: RendererClient, text: str, context: dict[str, Any], kind: RenderFailureKind
) -> None:
    assert (await renderer.render(text, context)).failure.kind == kind


async def test_renderer_request_failure_kind_is_understood(renderer: RendererClient) -> None:
    assert (await renderer._exchange(b"not json")).failure.kind == RenderFailureKind.REQUEST


@pytest.fixture
def socket_dir() -> Iterator[pathlib.Path]:
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        yield pathlib.Path(directory)


async def fake_renderer(
    socket_dir: pathlib.Path, settings: Settings, respond: Callable[[asyncio.StreamWriter], Awaitable[None]]
) -> tuple[RendererClient, asyncio.Server]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        size = struct.unpack(">I", await reader.readexactly(4))[0]
        await reader.readexactly(size)
        await respond(writer)
        writer.close()

    socket_path = str(socket_dir / "fake.sock")
    server = await asyncio.start_unix_server(handle, socket_path)
    client = RendererClient(settings)
    client.socket_path = socket_path
    client.timeout = 0.2
    return client, server


@pytest.mark.parametrize(
    ("frame", "kind"),
    [
        (b"", RenderFailureKind.CRASHED),
        (struct.pack(">I", MAX_REPLY_BYTES + 1), RenderFailureKind.INVALID_REPLY),
        (struct.pack(">I", 8) + b"not json", RenderFailureKind.INVALID_REPLY),
    ],
)
async def test_bad_replies_are_failures(
    settings: Settings, socket_dir: pathlib.Path, frame: bytes, kind: RenderFailureKind
) -> None:
    async def respond(writer: asyncio.StreamWriter) -> None:
        writer.write(frame)
        await writer.drain()

    client, server = await fake_renderer(socket_dir, settings, respond)
    async with server:
        reply = await client.render("x", {})
    assert not reply.ok
    assert reply.error is not None
    assert reply.error.kind == kind


async def test_per_call_timeout_overrides_the_default(settings: Settings, socket_dir: pathlib.Path) -> None:
    async def respond(writer: asyncio.StreamWriter) -> None:
        await asyncio.sleep(1)

    client, server = await fake_renderer(socket_dir, settings, respond)
    client.timeout = 30
    started = time.monotonic()
    async with server:
        with pytest.raises(exceptions.RendererUnavailableError):
            await client.render("x", {}, max_wait=0.1)
    assert time.monotonic() - started < 1


async def test_lightning_description_waits_less_than_other_templates(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer, mocker: pytest_mock.MockerFixture
) -> None:
    store_id = (await create_store(client, token))["id"]
    invoice = await (await container.get(InvoiceService)).get((await create_invoice(client, token, store_id=store_id))["id"])
    store = await load_store(container, store_id)
    render = mocker.spy(service.renderer, "render")
    await service.render_lightning_description(store, invoice, None)
    await service.render_notification(store, invoice)
    assert [call.kwargs["max_wait"] for call in render.call_args_list] == [LIGHTNING_DESCRIPTION_RENDER_TIMEOUT, None]


async def test_store_template_needs_an_owner(service: TemplateService) -> None:
    with pytest.raises(ValueError, match="needs an owner"):
        await service.render("shop", products=[])


async def test_unknown_template_raises(service: TemplateService) -> None:
    with pytest.raises(exceptions.TemplateDoesNotExistError):
        await service.render("nothing")


async def test_selection_beats_name_and_name_beats_default(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store_id = (await create_store(client, token))["id"]
    await save_template(client, token, "shop", "by name")
    selected = await save_template(client, token, "other", "by selection")
    store = await load_store(container, store_id)
    assert (await service.render("shop", owner=store, store=store, products=[])).text == "by name"
    resp = await client.patch(
        f"/stores/{store_id}", json={"templates": {"shop": selected["id"]}}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    await service.session.refresh(store)
    assert (await service.render("shop", owner=store, store=store, products=[])).text == "by selection"


async def test_product_selection_uses_owner(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store_id = (await create_store(client, token))["id"]
    template = await save_template(client, token, "special", "special {{ product.name }}")
    created = await create_product(client, token, store_id=store_id, name="Mug", templates={"product": template["id"]})
    product = await (await container.get(ProductService)).get(created["id"])
    store = await load_store(container, store_id)
    result = await service.render("product", owner=product, store=store, product=product, quantity=1)
    assert result.text == "special Mug"


async def test_failed_product_template_alerts_the_store_of_the_product(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store_id = (await create_store(client, token))["id"]
    template = await save_template(client, token, "special", "{{ 1 / 0 }}")
    created = await create_product(client, token, store_id=store_id, templates={"product": template["id"]})
    product = await (await container.get(ProductService)).get(created["id"])
    store = await load_store(container, store_id)
    result = await service.render("product", owner=product, store=store, product=product, quantity=1)
    assert result.is_fallback is True
    assert [alert.store_id for alert in alerts(service)] == [store_id]


@pytest.mark.parametrize("text", ["", "{% if false %}x{% endif %}"])
async def test_blank_custom_template_is_used_as_written_with_a_warning(
    client: TestClient,
    token: str,
    service: TemplateService,
    container: AsyncContainer,
    caplog: pytest.LogCaptureFixture,
    text: str,
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", text)
    with caplog.at_level(logging.WARNING):
        result = await service.render("shop", owner=store, store=store, products=[])
    assert result.text.strip() == ""
    assert result.is_fallback is False
    assert alerts(service) == []
    assert f'Template "shop" used as shop rendered empty text for store {store.id}' in caplog.text


async def test_external_failure_uses_default_and_alerts_separately(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", "first line\n{{ 1 / 0 }}")
    result = await service.render("shop", owner=store, store=store, products=[])
    assert result.is_fallback is True
    assert result.text.startswith("Welcome to our shop")
    assert "1 / 0" not in result.text
    sent = alerts(service)
    assert len(sent) == 1
    assert sent[0].store_id == store.id
    assert 'Template "shop"' in sent[0].text
    assert "Line 2: {{ 1 / 0 }}" in sent[0].text
    assert f"store=Store({store.id})" in sent[0].text


async def test_alerts_are_limited_per_template_and_store(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", "{{ 1 / 0 }}")
    await service.render("shop", owner=store, store=store, products=[])
    await service.render("shop", owner=store, store=store, products=[])
    assert len(alerts(service)) == 1


async def test_author_failure_puts_the_error_in_the_message(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store_id = (await create_store(client, token))["id"]
    invoice = await (await container.get(InvoiceService)).get((await create_invoice(client, token, store_id=store_id))["id"])
    store = await load_store(container, store_id)
    await save_template(client, token, "notification", "{{ 1 / 0 }}")
    result = await service.render("notification", owner=store, store=store, invoice=invoice)
    assert result.is_fallback is True
    assert result.text.startswith("New order from")
    assert "Line 1: {{ 1 / 0 }}" in result.text
    assert alerts(service) == []


async def test_failure_report_has_no_values(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", "rendered-part {{ 1 / 0 }}")
    await service.render("shop", owner=store, store=store, products=["product-secret"])
    text = alerts(service)[0].text
    assert "product-secret" not in text
    assert "products: list" in text


async def test_broken_default_raises(service: TemplateService, mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch.dict(
        service.template_manager.templates,
        {
            "broken": templates.Template(
                "broken",
                text="{{ 1 / 0 }}",
                applicable_to=TemplateScope.GLOBAL,
                audience=TemplateAudience.EXTERNAL,
                get_test_context=empty_test_context,
            )
        },
    )
    with pytest.raises(exceptions.TemplateRenderError):
        await service.render("broken")


async def test_unavailable_renderer_raises_and_alerts_superusers(
    client: TestClient,
    token: str,
    service: TemplateService,
    container: AsyncContainer,
    mocker: pytest_mock.MockerFixture,
    tmp_path: pathlib.Path,
) -> None:
    redis = await container.get(Redis)
    await redis.delete("template_alert:global:renderer")
    store = await load_store(container, (await create_store(client, token))["id"])
    mocker.patch.object(service.renderer, "socket_path", str(tmp_path / "missing.sock"))
    with pytest.raises(exceptions.RendererUnavailableError):
        await service.render("shop", owner=store, store=store, products=[])
    sent = alerts(service)
    assert len(sent) == 1
    assert sent[0].store_id is None
    await redis.delete("template_alert:global:renderer")


async def test_default_template_rejected_by_the_renderer_counts_as_unavailable(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer, mocker: pytest_mock.MockerFixture
) -> None:
    redis = await container.get(Redis)
    await redis.delete("template_alert:global:renderer")
    store = await load_store(container, (await create_store(client, token))["id"])
    reply = RendererReply.failed(RenderFailureKind.REQUEST, "request is invalid")
    mocker.patch.object(service.renderer, "render", return_value=reply)
    with pytest.raises(exceptions.RendererUnavailableError):
        await service.render("shop", owner=store, store=store, products=[])
    await redis.delete("template_alert:global:renderer")


async def test_metadata_writes_apply_only_to_passed_objects_on_success(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", "{{ update_metadata(store, 'seen', 'yes') and '' }}ok")
    assert (await service.render("shop", owner=store, store=store, products=[])).text == "ok"
    assert store.meta["seen"] == "yes"
    await client.patch(
        f"/templates/{(await service.get_or_none(None, name='shop', user_id=store.user_id)).id}",  # type: ignore[union-attr]
        json={
            "name": "shop",
            "text": "{{ delete_metadata(store, 'seen') and '' }}{{ update_metadata(store, 'x', 1) and '' }}{{ 1 / 0 }}",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert (await service.render("shop", owner=store, store=store, products=[])).is_fallback is True
    assert store.meta["seen"] == "yes"
    assert "x" not in store.meta


async def test_written_decimals_keep_every_digit(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    template = (
        "{{ update_metadata(store, 'one', price) and '' }}"
        "{{ update_metadata(store, 'many', {'a': [price, 1]}) and '' }}"
        "{{ get_metadata(store, 'one') }}"
    )
    await save_template(client, token, "shop", template)
    price = Decimal("0.123456789012345678")
    result = await service.render("shop", owner=store, store=store, products=[], price=price)
    assert result.text == "0.123456789012345678"
    assert store.meta["one"] == "0.123456789012345678"
    assert store.meta["many"] == {"a": ["0.123456789012345678", 1]}
    await save_template(client, token, "notification", "{{ get_metadata(store, 'one') | float * 2 }}")
    later = await service.render("notification", owner=store, store=store, invoice={})
    assert float(later.text) == float(price) * 2


async def test_forged_metadata_references_are_ignored(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    other = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", f"{{{{ update_metadata({{'_ref': 'Store:{other.id}'}}, 'x', 1) and '' }}}}ok")
    assert (await service.render("shop", owner=store, store=store, products=[])).text == "ok"
    assert "x" not in other.meta
    assert "x" not in store.meta


async def order_with_products(
    client: TestClient, token: str, container: AsyncContainer, **product_attrs: Any
) -> tuple[models.Store, models.Invoice]:
    store_id = (await create_store(client, token))["id"]
    product = await create_product(client, token, store_id=store_id, name="Mug <1>", **product_attrs)
    invoice = await create_invoice(client, token, store_id=store_id, products=[product["id"]], currency="USD")
    return (
        await load_store(container, store_id),
        await (await container.get(InvoiceService)).get(invoice["id"]),
    )


async def test_text_order_email(client: TestClient, token: str, service: TemplateService, container: AsyncContainer) -> None:
    store, invoice = await order_with_products(client, token, container)
    result = await service.render_order_email(store, invoice)
    assert result.is_html is False
    assert "Thanks for buying Mug <1> x 1!" in result.text


async def test_html_product_in_text_shop_converts_the_shop(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "<b>{{ product.name }}</b>", format="html")
    await save_template(client, token, "shop", "Hi <you>\n{% for p in products %}{{ p }}{% endfor %}")
    result = await service.render_order_email(store, invoice)
    assert result.is_html is True
    assert result.text == "Hi &lt;you&gt;<br>\n<b>Mug &lt;1&gt;</b>"


async def test_text_product_in_html_shop_is_converted(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "{{ product.name }}\nline")
    await save_template(
        client,
        token,
        "shop",
        "<h1>{{ store.name | upper }}</h1>{% for p in products %}<p>{{ p }}</p>{% endfor %}",
        format="html",
    )
    result = await service.render_order_email(store, invoice)
    assert result.is_html is True
    assert "<p>Mug &lt;1&gt;<br>\nline</p>" in result.text
    assert "BITCARTNESTED" not in result.text


@pytest.mark.parametrize(
    ("shop", "expected"),
    [
        ("{{ products[0] | replace('Mug', 'Cup') }}", "<b>Cup &lt;1&gt;</b>"),
        ("{{ products[0] | length }}", "20"),
        ("{% if 'Mug' in products[0] %}found{% endif %}", "found"),
    ],
)
async def test_html_shop_filters_see_the_real_product(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer, shop: str, expected: str
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "<b>{{ product.name }}</b>", format="html")
    await save_template(client, token, "shop", shop, format="html")
    assert (await service.render_order_email(store, invoice)).text == expected


@pytest.mark.parametrize("shop_format", ["text", "html"])
async def test_nested_fallback_carries_up_to_the_parent(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer, shop_format: str
) -> None:
    store = await load_store(container, (await create_store(client, token))["id"])
    await save_template(client, token, "shop", "{{ products[0] }}", format=shop_format)
    nested = RenderResult("part", is_fallback=True)
    assert (await service.render("shop", owner=store, store=store, products=[nested])).is_fallback is True
    assert (await service.render("shop", owner=store, store=store, products=[RenderResult("part")])).is_fallback is False


async def test_failed_html_shop_falls_back_with_products_and_one_note(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "<b>{{ product.name }}</b>", format="html")
    await save_template(client, token, "shop", "{{ 1 / 0 }}", format="html")
    result = await service.render_order_email(store, invoice)
    assert result.is_html is True
    assert result.is_fallback is True
    assert "<b>Mug &lt;1&gt;</b>" in result.text
    assert (
        result.text.count("Some details couldn&#x27;t be included")
        + result.text.count("Some details couldn&#39;t be included")
        == 1
    )


async def test_failed_product_adds_one_note_at_the_end(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "{{ 1 / 0 }}")
    result = await service.render_order_email(store, invoice)
    assert "Thanks for buying Mug <1> x 1!" in result.text
    assert result.text.count("Some details couldn't be included") == 1
    assert result.text.rstrip().endswith(f"Please contact {store.name}.")


async def test_broken_note_falls_back_to_default_note(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    await save_template(client, token, "product", "{{ 1 / 0 }}")
    await save_template(client, token, "fallback_note", "{{ 1 / 0 }}")
    result = await service.render_order_email(store, invoice)
    assert result.text.count("Some details couldn't be included") == 1
    assert {alert.text.split('"')[1] for alert in alerts(service)} == {"product", "fallback_note"}


async def test_rendering_does_not_round_the_product_price(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container, price="10.125")
    product = invoice.products_associations[0].product
    await save_template(client, token, "product", "{{ product.price }}")
    result = await service.render_order_email(store, invoice)
    assert "10.13" in result.text
    assert product.price == Decimal("10.125")
    assert not service.session.is_modified(product)


async def test_saving_invalid_syntax_is_refused(client: TestClient, token: str) -> None:
    resp = await client.post(
        "/templates", json={"name": "x", "text": "{% if %}"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422
    assert "syntax error" in resp.json()["detail"]


RENDERER_DOWN_REPLY = {"error": "Templates unavailable", "detail": "Templates are temporarily unavailable"}


async def test_saving_when_renderer_is_down_asks_to_retry(
    client: TestClient, token: str, app: FastAPI, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("api.services.renderer.RendererClient.check", side_effect=exceptions.RendererUnavailableError("down"))
    resp = await client.post("/templates", json={"name": "x", "text": "y"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
    assert resp.json() == RENDERER_DOWN_REPLY


async def test_empty_text_can_be_saved(client: TestClient, token: str) -> None:
    await save_template(client, token, "x", "")


async def run_test(client: TestClient, token: str, template_id: str, **data: Any) -> Any:
    return await client.post(f"/templates/{template_id}/test", json=data, headers={"Authorization": f"Bearer {token}"})


async def test_template_test_uses_generated_data_without_an_owner(client: TestClient, token: str) -> None:
    template = await save_template(client, token, "shop", "{{ store.name }} {{ products | length }}")
    resp = await run_test(client, token, template["id"])
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["text"] == "sample name 1"


async def test_template_test_generated_data_has_every_field(client: TestClient, token: str) -> None:
    text = "{{ store.theme_settings.logo }}|{{ invoice.payments[0].rate }}|{{ invoice.product_names | length }}"
    template = await save_template(client, token, "notification", text)
    assert (await run_test(client, token, template["id"])).json()["text"] == "|10.50|1"


async def test_template_test_uses_the_chosen_store(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    template = await save_template(client, token, "shop", "{{ store.name }}")
    resp = await run_test(client, token, template["id"], owner_id=store["id"])
    assert resp.json()["text"] == store["name"]
    assert (await run_test(client, token, template["id"], owner_id="missing")).status_code == 404


async def test_template_test_uses_the_named_product(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    product = await create_product(client, token, store_id=store["id"], name="Mug", price="10.125")
    await create_product(client, token, store_id=store["id"], name="Newer")
    template = await save_template(client, token, "product", "{{ store.name }}|{{ product.name }}|{{ product.price }}")
    resp = await run_test(client, token, template["id"], owner_id=product["id"])
    assert resp.json()["text"] == f"{store['name']}|Mug|10.13"


async def test_template_test_owner_must_match_the_scope(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    product = await create_product(client, token, store_id=store["id"])
    shop = await save_template(client, token, "shop", "x")
    assert (await run_test(client, token, shop["id"], owner_id=product["id"])).status_code == 404
    product_template = await save_template(client, token, "product", "x")
    assert (await run_test(client, token, product_template["id"], owner_id=store["id"])).status_code == 404


async def test_template_test_hides_owners_of_other_users(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    user = await create_user(client, token=token, is_superuser=False)
    user_token = (await create_token(client, user))["access_token"]
    theirs = await save_template(client, user_token, "shop", "{{ store.name }}")
    assert (await run_test(client, user_token, theirs["id"], owner_id=store["id"])).status_code == 404
    own_store = await create_store(client, user_token)
    resp = await run_test(client, user_token, theirs["id"], owner_id=own_store["id"])
    assert resp.json()["text"] == own_store["name"]
    ours = await save_template(client, token, "shop", "{{ store.name }}")
    assert (await run_test(client, token, ours["id"], owner_id=own_store["id"])).json()["text"] == own_store["name"]


async def test_template_test_global_template_ignores_the_owner(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    user = (await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})).json()
    template = await save_template(client, token, "forgotpassword", "{{ email }}|{{ link }}|{{ code }}|{{ store }}")
    resp = await run_test(client, token, template["id"], owner_id=store["id"])
    assert resp.json()["text"] == f"{user['email']}|sample link|sample code|"


async def test_template_test_prefers_the_newest_complete_invoice(
    client: TestClient, token: str, container: AsyncContainer
) -> None:
    store = await create_store(client, token)
    template = await save_template(client, token, "notification", "{{ invoice.id }}")
    resp = await run_test(client, token, template["id"], owner_id=store["id"])
    assert resp.json()["text"] == "sample id"
    invoices = await container.get(InvoiceService)
    complete = await create_invoice(client, token, store_id=store["id"])
    newer_pending = await create_invoice(client, token, store_id=store["id"])
    assert (await run_test(client, token, template["id"], owner_id=store["id"])).json()["text"] == newer_pending["id"]
    (await invoices.get(complete["id"])).status = InvoiceStatus.COMPLETE
    await invoices.session.commit()
    assert (await run_test(client, token, template["id"], owner_id=store["id"])).json()["text"] == complete["id"]


async def test_template_test_uses_the_newest_refund_and_its_invoice(
    client: TestClient, token: str, container: AsyncContainer
) -> None:
    store = await create_store(client, token)
    with_refund = await create_invoice(client, token, store_id=store["id"], currency="USD")
    newer = await create_invoice(client, token, store_id=store["id"])
    text = "{{ refund | format_decimal('amount') }}|{{ invoice.id }}|{{ refund_url }}"
    template = await save_template(client, token, "customer_refund", text)
    resp = await run_test(client, token, template["id"], owner_id=store["id"])
    assert resp.json()["text"] == f"10.50|{newer['id']}|sample refund_url"
    session = (await container.get(InvoiceService)).session
    session.add(models.Refund(amount=Decimal(3), currency="USD", invoice_id=with_refund["id"]))
    await session.commit()
    resp = await run_test(client, token, template["id"], owner_id=store["id"])
    assert resp.json()["text"] == f"3.00|{with_refund['id']}|sample refund_url"


async def test_template_test_shop_uses_default_product_template(
    client: TestClient, token: str, service: TemplateService, container: AsyncContainer
) -> None:
    store, invoice = await order_with_products(client, token, container)
    product_id = invoice.products_associations[0].product_id
    await save_template(client, token, "product", "{{ update_metadata(product, 'x', 1) and '' }}{{ 1 / 0 }}")
    template = await save_template(client, token, "shop", "<p>{{ products[0] }}</p>", format="html")
    resp = await run_test(client, token, template["id"], owner_id=store.id)
    assert resp.json()["text"].startswith("<p>Thanks for buying Mug &lt;1&gt; x 1!")
    assert alerts(service) == []
    product = await client.get(f"/products/{product_id}", headers={"Authorization": f"Bearer {token}"})
    assert product.json()["metadata"] == {}


async def table_sizes(container: AsyncContainer) -> dict[str, int]:
    session = (await container.get(InvoiceService)).session
    tables = models.Model.metadata.sorted_tables
    return {table.name: (await session.execute(select(func.count()).select_from(table))).scalar_one() for table in tables}


async def test_template_test_does_not_save_generated_data(client: TestClient, token: str, container: AsyncContainer) -> None:
    store = await create_store(client, token)
    await create_invoice(client, token, store_id=store["id"])
    tested = [await save_template(client, token, name, "x") for name in ("notification", "customer_refund", "shop")]
    before = await table_sizes(container)
    for template in tested:
        assert (await run_test(client, token, template["id"])).json()["ok"]
        assert (await run_test(client, token, template["id"], owner_id=store["id"])).json()["ok"]
    assert await table_sizes(container) == before


async def test_template_test_calls_the_template_callback(
    client: TestClient, token: str, app: FastAPI, mocker: pytest_mock.MockerFixture
) -> None:
    received: list[TemplateTestData[models.Store]] = []

    async def get_test_context(data: TemplateTestData[models.Store]) -> dict[str, Any]:
        received.append(data)
        return {"value": "from callback"}

    manager = await app.state.dishka_container.get(TemplateManager)
    plugin_template = templates.Template(
        "plugin_template",
        text="x",
        applicable_to=TemplateScope.STORE,
        audience=TemplateAudience.EXTERNAL,
        get_test_context=get_test_context,
    )
    mocker.patch.dict(manager.templates, {"plugin_template": plugin_template})
    store = await create_store(client, token)
    template = await save_template(client, token, "plugin_template", "{{ value }}")
    assert (await run_test(client, token, template["id"], owner_id=store["id"])).json()["text"] == "from callback"
    assert received[0].owner is not None
    assert received[0].owner.id == store["id"]
    assert (await run_test(client, token, template["id"])).json()["text"] == "from callback"
    assert received[1].owner is None


async def test_template_test_does_not_apply_writes(client: TestClient, token: str) -> None:
    store = await create_store(client, token)
    template = await save_template(client, token, "shop", "{{ update_metadata(store, 'x', 1) and '' }}ok")
    assert (await run_test(client, token, template["id"], owner_id=store["id"])).json()["text"] == "ok"
    resp = await client.get(f"/stores/{store['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["metadata"] == {}
