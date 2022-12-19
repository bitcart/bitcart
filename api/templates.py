from collections import defaultdict

from jinja2 import Template as JinjaTemplate
from jinja2 import TemplateError

from api.exceptions import TemplateLoadError


class Template:
    def __init__(self, name, text=None, applicable_to="", prefix="api/templates"):
        self.prefix = prefix
        self.name = name
        self.applicable_to = applicable_to
        if text:
            self.template_text = text
        else:
            self.load_from_file(name)
        self.template = JinjaTemplate(self.template_text, trim_blocks=True)

    def load_from_file(self, name):
        try:
            with open(f"{self.prefix}/{name}.j2") as f:
                self.template_text = f.read().strip()
        except OSError as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e.strerror}")

    def render(self, *args, **kwargs):
        try:
            return self.template.render(*args, **kwargs)
        except TemplateError:
            return ""


ProductTemplate = Template("product", applicable_to="product")
BaseShopTemplate = Template("shop", applicable_to="store")
NotificationTemplate = Template("notification", applicable_to="store")


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
