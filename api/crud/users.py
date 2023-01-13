from fastapi import HTTPException

from api import models, schemes, settings, utils
from api.constants import SHORT_EXPIRATION
from api.db import db
from api.plugins import run_hook

RESET_REDIS_KEY = "reset_password"


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
    d.pop("captcha_code", None)
    obj = await utils.database.create_object(models.User, d)
    if is_superuser and auth_user is None:
        await run_hook("first_user", obj)
    return obj


async def reset_user_password(user, next_url):
    policy = await utils.policies.get_setting(schemes.Policy)
    email_settings = policy.email_settings
    args = (
        email_settings.get("email_host"),
        email_settings.get("email_port"),
        email_settings.get("email_user"),
        email_settings.get("email_password"),
        email_settings.get("email"),
        email_settings.get("email_use_ssl"),
    )
    if not utils.email.check_ping(*args):  # pragma: no cover
        return True
    code = utils.common.unique_id()
    async with utils.redis.wait_for_redis():
        await settings.settings.redis_pool.set(f"{RESET_REDIS_KEY}:{code}", user.id, ex=SHORT_EXPIRATION)
    reset_url = utils.routing.get_redirect_url(next_url, code=code)
    # TODO: switch to get_template and allow customizing for server admins only
    template = settings.settings.template_manager.templates["forgotpassword"]
    email_text = template.render(email=user.email, link=reset_url)
    utils.email.send_mail(*args, user.email, email_text, "Password reset")
    await run_hook("password_reset_requested", user, code)


async def change_password(user, password, logout_all=True):
    await utils.database.modify_object(user, {"password": password})
    if logout_all:
        await models.Token.delete.where(models.Token.user_id == user.id).gino.status()
    await run_hook("password_changed", user)
