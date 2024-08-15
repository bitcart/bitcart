from typing import Optional

from fastapi import APIRouter

from api import models, schemes, settings, utils
from api.utils.common import prepare_compliant_response

router = APIRouter(tags=["templates"])


@router.get("/list")
async def get_template_list(applicable_to: Optional[str] = None, show_all: bool = False):
    result_set = settings.settings.template_manager.templates_strings
    if applicable_to:
        result_set = result_set.get(applicable_to, [])
    elif show_all:
        result_set = [v for template_set in result_set.values() for v in template_set]
    return prepare_compliant_response(result_set)


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.Template,
    schemes.UpdateTemplate,
    schemes.CreateTemplate,
    schemes.DisplayTemplate,
    scopes=["template_management"],
)
