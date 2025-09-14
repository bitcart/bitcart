from typing import Any, cast

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from api.constants import AuthScopes
from api.schemas.templates import CreateTemplate, DisplayTemplate, UpdateTemplate
from api.services.crud.templates import TemplateService
from api.templates import TemplateManager
from api.utils.common import prepare_compliant_response
from api.utils.routing import create_crud_router

router = APIRouter(route_class=DishkaRoute)


@router.get("/list")
async def get_template_list(
    template_manager: FromDishka[TemplateManager], applicable_to: str | None = None, show_all: bool = False
) -> Any:
    templates_strings = template_manager.templates_strings
    if applicable_to:
        result_set = templates_strings.get(applicable_to, [])
    elif show_all:
        result_set = [v for template_set in templates_strings.values() for v in template_set]
    else:
        result_set = cast(list[str], templates_strings)
    return prepare_compliant_response(result_set)


create_crud_router(
    CreateTemplate,
    UpdateTemplate,
    DisplayTemplate,
    TemplateService,
    router=router,
    required_scopes=[AuthScopes.TEMPLATE_MANAGEMENT],
)
