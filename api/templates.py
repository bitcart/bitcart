from collections import defaultdict
from typing import Any

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from api.exceptions import TemplateLoadError
from api.ext.moneyformat import currency_table
from api.logging import get_exception_message, get_logger
from api.plugins import delete_metadata, get_metadata, update_metadata

logger = get_logger(__name__)


def format_decimal(obj: Any, key: str, **kwargs: Any) -> Any:  # pragma: no cover
    if not hasattr(obj, key):
        return ""
    value = getattr(obj, key)
    if not hasattr(obj, "currency"):
        return value
    return currency_table.normalize(obj.currency, value)


sandbox = SandboxedEnvironment(trim_blocks=True)
sandbox.filters["format_decimal"] = format_decimal
sandbox.globals["get_metadata"] = get_metadata
sandbox.globals["update_metadata"] = update_metadata
sandbox.globals["delete_metadata"] = delete_metadata


class Template:
    def __init__(self, name: str, text: str | None = None, applicable_to: str = "", prefix: str = "api/templates") -> None:
        self.prefix = prefix
        self.name = name
        self.applicable_to = applicable_to
        if text:
            self.template_text = text
        else:
            self.load_from_file(name)
        self.template = sandbox.from_string(self.template_text)

    def load_from_file(self, name: str) -> None:
        try:
            with open(f"{self.prefix}/{name}.j2") as f:
                self.template_text = f.read().strip()
        except OSError as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e.strerror}") from e

    def render(self, *args: Any, **kwargs: Any) -> str:
        try:
            return self.template.render(*args, **kwargs)
        except TemplateError as e:
            logger.error(f"Failed to render template {self.name}: {get_exception_message(e)}")
            return ""


ProductTemplate = Template("product", applicable_to="product")
BaseShopTemplate = Template("shop", applicable_to="store")
NotificationTemplate = Template("notification", applicable_to="store")
ForgotPasswordTemplate = Template("forgotpassword", applicable_to="global")
VerifyEmailTemplate = Template("verifyemail", applicable_to="global")
CustomerRefundTemplate = Template("customer_refund", applicable_to="store")
MerchantRefundNotifyTemplate = Template("merchant_refund_notify", applicable_to="store")

ALL_TEMPLATES = {template.name: template for template in globals().values() if isinstance(template, Template)}


class TemplateManager:
    def __init__(self) -> None:
        self.init_defaults()

    def add_template(self, template: Template) -> None:
        self.templates[template.name] = template
        self.templates_strings[template.applicable_to].append(template.name)

    def init_defaults(self) -> None:
        self.templates = ALL_TEMPLATES
        self.templates_strings = defaultdict(list)
        for template in self.templates.values():
            self.templates_strings[template.applicable_to].append(template.name)
