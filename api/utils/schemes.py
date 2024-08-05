from pydantic import BaseModel, create_model


# For PATCH requests
def to_optional(model: type[BaseModel]) -> type[BaseModel]:
    new_model = create_model(f"Optional{model.__name__}", __base__=model)

    for field in new_model.__fields__.values():
        field.required = False
    return new_model
