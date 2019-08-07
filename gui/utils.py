from os.path import join as path_join
from typing import Callable, Dict, List, Type, Union
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


HTTP_METHODS: List[str] = ["GET",
                           "POST",
                           "PUT",
                           "PATCH",
                           "DELETE"]


def model_view(router: APIRouter,
               path: str,
               orm_model,
               pydantic_model,
               create_model=None,
               allowed_methods: List[str] = ["GET_ONE"] + HTTP_METHODS,
               custom_methods: Dict[str, Callable] = {}):
    if not create_model:
        create_model = pydantic_model
    response_models: Dict[str, Type] = {
        "get": List[pydantic_model],  # type: ignore
        "get_one": pydantic_model,
        "post": pydantic_model,
        "put": pydantic_model,
        "patch": pydantic_model,
        "delete": pydantic_model}

    item_path = path_join(path, "{model_id}")
    paths: Dict[str,
                str] = {"get": path,
                        "get_one": item_path,
                        "post": path,
                        "put": item_path,
                        "patch": item_path,
                        "delete": item_path}

    async def get():
        return await orm_model.query.gino.all()

    async def get_one(model_id: Union[int, str]):
        item = await orm_model.get(model_id)
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Object with id {model_id} does not exist!")
        return item

    async def post(model: create_model):  # type: ignore
        return await orm_model.create(**model.dict())  # type: ignore

    async def put(model_id: Union[int, str], model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        await item.update(**model.dict()).apply()  # type: ignore
        return item

    async def patch(model_id: Union[int, str], model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        await item.update(**model.dict(skip_defaults=True)).apply()  # type: ignore # noqa
        return item

    async def delete(model_id: Union[int, str]):
        item = await get_one(model_id)
        await item.delete()
        return item

    for method in allowed_methods:
        method_name = method.lower()
        router.add_api_route(  # type: ignore
            paths.get(method_name),
            custom_methods.get(method_name) or locals()[method_name],
            methods=[method_name if method_name in HTTP_METHODS else "get"],
            response_model=response_models.get(method_name))
