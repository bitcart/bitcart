from jinja2 import Template as JinjaTemplate
from jinja2 import TemplateError
from .exceptions import TemplateLoadError


class Template:
    def __init__(self, name, text=None):
        self.name = name
        if text:
            self.template_text = text
        else:
            self.load_from_file(name)
        self.template = JinjaTemplate(self.template_text, trim_blocks=True)

    def load_from_file(self, name):
        try:
            with open(f"api/templates/{name}.j2") as f:
                self.template_text = f.read()
        except OSError as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e.strerror}")

    def render(self, *args, **kwargs):
        try:
            return self.template.render(*args, **kwargs)
        except TemplateError:
            return ""


ProductTemplate = Template("email_product")
BaseShopTemplate = Template("email_base_shop")
NotificationTemplate = Template("notification")

templates = {
    template.name: template
    for template in globals().values()
    if isinstance(template, Template)
}
templates_strings = [template for template in templates]
