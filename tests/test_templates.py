import pytest

from api import exceptions, templates


class DummyInvoice:
    buyer_email = "test@test.com"


def test_default_template_render(notification_template):
    template = templates.Template("notification")
    assert template.name == "notification"
    assert template.template_text == notification_template
    assert template.render() == ""  # Silent error handling
    assert template.render(invoice=DummyInvoice()) == "New order from test@test.com"


def test_unknown_template_render():
    with pytest.raises(exceptions.TemplateLoadError):
        templates.Template("test")


def test_text_template_render():
    template = templates.Template("test", "Hello {{var}}!")
    assert template.name == "test"
    assert template.template_text == "Hello {{var}}!"
    assert template.render() == "Hello !"
    assert template.render(var="world") == "Hello world!"


def test_add_template():
    manager = templates.TemplateManager()
    template = templates.Template("product")
    manager.add_template(template)
    assert manager.templates["product"] == template
