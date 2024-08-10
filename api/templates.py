from collections import defaultdict

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from api.exceptions import TemplateLoadError
from api.ext.moneyformat import currency_table
from api.logger import get_exception_message, get_logger


def format_decimal(obj, key, **kwargs):  # pragma: no cover
    if not hasattr(obj, key):
        return ""
    value = getattr(obj, key)
    if not hasattr(obj, "currency"):
        return value
    return currency_table.normalize(obj.currency, value)


sandbox = SandboxedEnvironment(trim_blocks=True)
sandbox.filters["format_decimal"] = format_decimal

logger = get_logger(__name__)


class Template:
    def __init__(self, name, text=None, applicable_to="", prefix="api/templates"):
        self.prefix = prefix
        self.name = name
        self.applicable_to = applicable_to
        if text:
            self.template_text = text
        else:
            self.load_from_file(name)
        self.template = sandbox.from_string(self.template_text)

    def load_from_file(self, name):
        try:
            with open(f"{self.prefix}/{name}.j2") as f:
                self.template_text = f.read().strip()
        except OSError as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e.strerror}")

    def render(self, *args, **kwargs):
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


class TemplateManager:
    def __init__(self):
        self.init_defaults()

    def add_template(self, template):
        self.templates[template.name] = template
        self.templates_strings[template.applicable_to].append(template.name)

    def init_defaults(self):
        self.templates = {template.name: template for template in globals().values() if isinstance(template, Template)}
        self.templates_strings = defaultdict(list)
        for template in self.templates.values():
            self.templates_strings[template.applicable_to].append(template.name)
