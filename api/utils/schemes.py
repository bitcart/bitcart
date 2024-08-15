from pydantic import BaseModel, create_model


# For PATCH requests
def to_optional(model: type[BaseModel]) -> type[BaseModel]:
    optional_fields = {field_name: (model_field.annotation, None) for field_name, model_field in model.model_fields.items()}
    return create_model(f"Optional{model.__name__}", __base__=model, **optional_fields)
