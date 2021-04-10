from typing import Optional

from fastapi import APIRouter

from .. import crud, models, schemes, templates, utils

router = APIRouter()


@router.get("/list")
async def get_template_list(applicable_to: Optional[str] = None, show_all: bool = False):
    result_set = templates.templates_strings
    if applicable_to:
        result_set = result_set.get(applicable_to, [])
    elif show_all:
        result_set = [v for template_set in result_set.values() for v in template_set]
    return {
        "count": len(result_set),
        "next": None,
        "previous": None,
        "result": result_set,
    }


utils.routing.ModelView.register(
    router,
    "/",
    models.Template,
    schemes.Template,
    schemes.CreateTemplate,
    custom_methods={"post": crud.templates.create_template},
    scopes=["template_management"],
)
