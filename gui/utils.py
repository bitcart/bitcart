from os.path import join as path_join
from typing import Callable, Dict, List, Type, Union
from gino.loader import ModelLoader
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def model_view(router: APIRouter,
               path: str,
               orm_model,
               pydantic_model,
               create_model=None,
               allowed_methods: List[str] = [
                   "GET",
                   "POST",
                   "PUT",
                   "PATCH",
                   "DELETE"],
               custom_methods: Dict[str, Callable] = {}):
    if not create_model:
        create_model = pydantic_model
    response_models: Dict[str, Type] = {
        "get": List[pydantic_model],  # type: ignore
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
        query = orm_model.query
        parent = orm_model.parent()
        print(parent)
        parents = await query.gino.load(parent.distinct(parent.id).load(add_child=orm_model.distinct(orm_model.id))).all()
        # print(help(orm_model.query.gino.load))
        # orm_model.
        #query = orm_model.query
        #query = query.execution_options(loader=orm_model)
        # items = await query.gino.all()
        # print(items)
        # print((await items[0].load().gino.all())[0].user)
        # return items
        # print(itemsuser)
        print("X", parents)
        return await orm_model.query.gino.all()

    async def get_one(model_id: Union[int, str]):
        item = await orm_model.get(model_id)
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Object with id {model_id} does not exist!")
        return item

    async def post(model: create_model):  # type: ignore
        print(model.dict())
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
        if method_name == "get":
            router.add_api_route(  # type: ignore
                paths.get("get_one"),
                get_one,
                methods=["get"],
                response_model=pydantic_model)
        router.add_api_route(  # type: ignore
            paths.get(method_name),
            custom_methods.get(method_name) or locals()[method_name],
            methods=[method_name],
            response_model=response_models.get(method_name))
