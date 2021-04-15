import json

from api import models
from api.utils.time import now


async def get_setting(scheme):
    name = scheme.__name__.lower()
    item = await models.Setting.query.where(models.Setting.name == name).gino.first()
    if not item:
        return scheme()
    return scheme(**json.loads(item.value))


async def set_setting(scheme):
    name = scheme.__class__.__name__.lower()
    json_data = scheme.dict(exclude_unset=True)
    data = {"name": name, "value": json_data}
    model = await models.Setting.query.where(models.Setting.name == name).gino.first()
    if model:
        value = json.loads(model.value)
        for key in json_data:
            value[key] = json_data[key]
        data["value"] = json.dumps(value)
        await model.update(**data).apply()
    else:
        data["value"] = json.dumps(json_data)
        await models.Setting.create(**data, created=now())
    return scheme
