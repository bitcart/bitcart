import enum
import html
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from api.exceptions import TemplateLoadError

if TYPE_CHECKING:
    from api.templates.context import TemplateContextGetter


class TemplateFormat(enum.StrEnum):
    TEXT = "text"
    HTML = "html"


class TemplateAudience(enum.StrEnum):
    AUTHOR = "author"
    EXTERNAL = "external"


class TemplateScope(enum.StrEnum):
    GLOBAL = "global"
    STORE = "store"
    PRODUCT = "product"


def text_to_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>\n")


@dataclass(frozen=True)
class RenderResult:
    text: str
    is_html: bool = False
    is_fallback: bool = False

    def as_html(self) -> "RenderResult":
        return self if self.is_html else RenderResult(text_to_html(self.text), True, self.is_fallback)

    def with_note(self, note: "RenderResult") -> "RenderResult":
        if self.is_html or note.is_html:
            return RenderResult(f"{self.as_html().text}<br>\n<br>\n{note.as_html().text}", True, True)
        return RenderResult(f"{self.text}\n\n{note.text}", False, True)


class Template:
    def __init__(
        self,
        name: str,
        *,
        applicable_to: TemplateScope,
        audience: TemplateAudience,
        get_test_context: "TemplateContextGetter[Any]",
        text: str | None = None,
        prefix: str = "api/templates/defaults",
    ) -> None:
        self.name = name
        self.applicable_to = applicable_to
        self.audience = audience
        self.get_test_context = get_test_context
        self.prefix = prefix
        self.text = text or self.load_from_file(name)

    def load_from_file(self, name: str) -> str:
        try:
            with open(f"{self.prefix}/{name}.j2") as f:
                return f.read().strip()
        except OSError as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e.strerror}") from e


class TemplateManager:
    def __init__(self, templates: Iterable[Template]) -> None:
        self.templates: dict[str, Template] = {}
        self.templates_strings: defaultdict[str, list[str]] = defaultdict(list)
        for template in templates:
            self.add_template(template)

    def add_template(self, template: Template) -> None:
        if template.name not in self.templates:
            self.templates_strings[template.applicable_to].append(template.name)
        self.templates[template.name] = template
