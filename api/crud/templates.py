from .. import models, schemes


async def create_template(template: schemes.CreateTemplate, user: schemes.User):
    return await models.Template.create(**template.dict(), user_id=user.id)
