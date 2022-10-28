from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import SecurityScopes
from sqlalchemy import distinct, func, select

from api import crud, db, models, schemes, utils

router = APIRouter()


@router.get("/stats")
async def get_stats(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["full_control"])):
    queries = []
    output_formats = []
    for index, orm_model in enumerate(utils.routing.ModelView.crud_models):
        label = orm_model.__name__.lower() + "s"  # based on naming convention, i.e. User->users
        query = select([func.count(distinct(orm_model.id))])
        if orm_model != models.User:
            query = query.where(orm_model.user_id == user.id)
        queries.append(query.label(label))
        output_formats.append((label, index))
    result = await db.db.first(select(queries))
    response = {key: result[ind] for key, ind in output_formats}
    response.pop("users", None)
    return response


@router.get("/me", response_model=schemes.DisplayUser)
async def get_me(user: models.User = Security(utils.authorization.AuthDependency())):
    return user


@router.post("/me/settings", response_model=schemes.User)
async def set_settings(
    settings: schemes.UserPreferences,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["full_control"]),
):
    await user.set_json_key("settings", settings)
    return user


class CreateUserWithToken(schemes.DisplayUser):
    token: str


async def create_user(model: schemes.CreateUser, request: Request):
    try:
        auth_user = await utils.authorization.AuthDependency()(request, SecurityScopes([]))
    except HTTPException:
        auth_user = None
    user = await crud.users.create_user(model, auth_user)
    token = await utils.database.create_object(
        models.Token, schemes.CreateDBToken(permissions=["full_control"], user_id=user.id)
    )
    data = schemes.DisplayUser.from_orm(user).dict()
    data["token"] = token.id
    return data


utils.routing.ModelView.register(
    router,
    "/",
    models.User,
    schemes.User,
    schemes.CreateUser,
    display_model=schemes.DisplayUser,
    custom_methods={"post": crud.users.create_user},
    post_auth=False,
    request_handlers={"post": create_user},
    response_models={"post": CreateUserWithToken},
    scopes={
        "get_all": ["server_management"],
        "get_count": ["server_management"],
        "get_one": ["server_management"],
        "post": [],
        "patch": ["server_management"],
        "delete": ["server_management"],
    },
)
