from fastapi import HTTPException

from api import models, schemes, settings, utils
from api.constants import SHORT_EXPIRATION, VERIFY_EMAIL_EXPIRATION
from api.db import db
from api.plugins import run_hook

RESET_REDIS_KEY = "reset_password"
VERIFY_REDIS_KEY = "verify_email"


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()


async def create_user(user: schemes.CreateUser, auth_user: schemes.User):
    register_off = (await utils.policies.get_setting(schemes.Policy)).disable_registration
    if register_off and (not auth_user or not auth_user.is_superuser):
        raise HTTPException(422, "Registration disabled")
    if not auth_user or not auth_user.is_superuser:
        await utils.authorization.captcha_flow(user.captcha_code)
    is_superuser = False
    if auth_user is None:
        count = await user_count()
        is_superuser = True if count == 0 else False
    elif auth_user and auth_user.is_superuser:
        is_superuser = user.is_superuser
    d = user.dict()
    d["is_superuser"] = is_superuser
    for key in ("verify_url", "captcha_code"):
        d.pop(key, None)
    obj = await utils.database.create_object(models.User, d)
    if is_superuser and auth_user is None:
        await run_hook("first_user", obj)
    return obj


async def generic_email_code_flow(
    redis_key, template_name, email_title, hook_name, user, next_url, expire_time=SHORT_EXPIRATION
):
    policy = await utils.policies.get_setting(schemes.Policy)
    email_obj = utils.email.Email.get_email(policy)

    if not email_obj.is_enabled():  # pragma: no cover
        return
    code = utils.common.unique_id()
    async with utils.redis.wait_for_redis():
        await settings.settings.redis_pool.set(f"{redis_key}:{code}", user.id, ex=expire_time)
    reset_url = utils.routing.get_redirect_url(next_url, code=code)
    # TODO: switch to get_template and allow customizing for server admins only
    template = settings.settings.template_manager.templates[template_name]
    text = template.render(email=user.email, link=reset_url)
    email_obj.send_mail(user.email, text, email_title)
    await run_hook(f"{hook_name}_requested", user, code)


async def reset_user_password(user, next_url):
    await generic_email_code_flow(RESET_REDIS_KEY, "forgotpassword", "Password reset", "password_reset", user, next_url)


async def send_verification_email(user, next_url, expire_time=VERIFY_EMAIL_EXPIRATION):
    await generic_email_code_flow(
        VERIFY_REDIS_KEY, "verifyemail", "Verify email", "verify_email", user, next_url, expire_time=expire_time
    )


async def change_password(user, password, logout_all=True):
    await utils.database.modify_object(user, {"password": password})
    if logout_all:
        await models.Token.delete.where(models.Token.user_id == user.id).gino.status()
    await run_hook("password_changed", user)
