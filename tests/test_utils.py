import aioredis
import pytest

from api import exceptions, settings, utils


def test_verify_password():
    p_hash = utils.get_password_hash("12345")
    assert isinstance(p_hash, str)
    assert utils.verify_password("12345", p_hash)


async def reader(chan):
    while await chan.wait_message():
        msg = await chan.get_json()
        assert msg == {"hello": "world"}
        break


@pytest.mark.asyncio
async def test_auth_dependency():
    dep = utils.AuthDependency(enabled=False)
    assert not await dep(None, None)


@pytest.mark.asyncio
async def test_make_subscriber():
    sub, chan = await utils.make_subscriber("test")
    assert sub is not None
    assert chan is not None
    assert isinstance(sub, aioredis.Redis)
    assert isinstance(chan, aioredis.Channel)
    await sub.subscribe("channel:test")
    settings.loop.create_task(reader(chan))
    assert await utils.publish_message("test", {"hello": "world"}) == 1


class MockStore:
    templates = {"notification": 1}


@pytest.mark.asyncio
async def test_get_template(notification_template, async_client, token):
    template = await utils.get_template("notification")
    assert template.name == "notification"
    assert template.template_text == notification_template
    assert template.render() == ""
    with pytest.raises(exceptions.TemplateDoesNotExistError):
        await utils.get_template("templ")
    resp = await async_client.post(
        "/templates",
        json={"name": "templ", "text": "Hello {{var1}}!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template2 = await utils.get_template("templ")
    assert template2.name == "templ"
    assert template2.template_text == "Hello {{var1}}!"
    assert template2.render() == "Hello !"
    assert template2.render(var1="world") == "Hello world!"
    template3 = await utils.get_template("notification", obj=MockStore())
    assert template3.name == "notification"
    assert template3.template_text == template2.template_text
    await async_client.delete(
        "/templates/1", headers={"Authorization": f"Bearer {token}"}
    )  # cleanup
