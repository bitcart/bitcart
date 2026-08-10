from decimal import Decimal

import pytest

from api import exceptions, templates


class DummyInvoice:
    buyer_email = "test@test.com"


class DummyPricedInvoice:
    currency = "USD"
    price = Decimal("10.5")


def test_default_template_render(notification_template: str) -> None:
    template = templates.Template("notification")
    assert template.name == "notification"
    assert template.template_text == notification_template
    assert template.render() == ""  # Silent error handling
    assert template.render(invoice=DummyInvoice()) == "New order from test@test.com for  !"


def test_unknown_template_render() -> None:
    with pytest.raises(exceptions.TemplateLoadError):
        templates.Template("test")


def test_text_template_render() -> None:
    template = templates.Template("test", "Hello {{var}}!")
    assert template.name == "test"
    assert template.template_text == "Hello {{var}}!"
    assert template.render() == "Hello !"
    assert template.render(var="world") == "Hello world!"


def test_add_template() -> None:
    manager = templates.TemplateManager()
    template = templates.Template("product")
    manager.add_template(template)
    assert manager.templates["product"] == template


def test_format_decimal_legitimate_field() -> None:
    template = templates.Template("test", '{{ invoice | format_decimal("price") }}')
    assert template.render(invoice=DummyPricedInvoice()) == "10.50"


def test_format_decimal_attribute_isolation() -> None:
    template = templates.Template("test", '{{ namespace() | format_decimal("__class__") }}')
    assert template.render() == ""

    chained = (
        '{% set a = namespace() | format_decimal("__class__") %}'
        '{% set b = a | format_decimal("__init__") %}'
        '{% set c = b | format_decimal("__globals__") %}'
        "{{ c }}"
    )
    assert templates.Template("test", chained).render() == ""
