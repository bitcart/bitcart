import os
import shlex
import subprocess
import time
from dataclasses import dataclass

import aioredis
import pytest

from api import exceptions, settings, utils


def test_verify_password():
    p_hash = utils.authorization.get_password_hash("12345")
    assert isinstance(p_hash, str)
    assert utils.authorization.verify_password("12345", p_hash)


async def reader(chan):
    while await chan.wait_message():
        msg = await chan.get_json()
        assert msg == {"hello": "world"}
        break


@pytest.mark.asyncio
async def test_auth_dependency():
    dep = utils.authorization.AuthDependency(enabled=False)
    assert not await dep(None, None)


@pytest.mark.asyncio
async def test_make_subscriber():
    sub, chan = await utils.redis.make_subscriber("test")
    assert sub is not None
    assert chan is not None
    assert isinstance(sub, aioredis.Redis)
    assert isinstance(chan, aioredis.Channel)
    await sub.subscribe("channel:test")
    settings.loop.create_task(reader(chan))
    assert await utils.redis.publish_message("test", {"hello": "world"}) == 1


@dataclass
class MockTemplateObj:
    template_name: str
    create_id: int
    mock_name: str = "MockTemplateObj"
    user_id: int = 1
    id: int = 1

    @property
    def templates(self):
        return {self.template_name: self.create_id}

    def __str__(self):
        return self.mock_name


class MockStore:
    user_id = 1

    def __str__(self):
        return "MockStore"


@pytest.mark.asyncio
async def test_get_template(notification_template, async_client, token):
    template = await utils.templates.get_template("notification")
    assert template.name == "notification"
    assert template.template_text == notification_template
    assert template.render() == ""
    with pytest.raises(exceptions.TemplateDoesNotExistError):
        await utils.templates.get_template("templ")
    resp = await async_client.post(
        "/templates",
        json={"name": "templ", "text": "Hello {{var1}}!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template2 = await utils.templates.get_template("templ", user_id=1)
    assert template2.name == "templ"
    assert template2.template_text == "Hello {{var1}}!"
    assert template2.render() == "Hello !"
    assert template2.render(var1="world") == "Hello world!"
    template3 = await utils.templates.get_template(
        "notification", obj=MockTemplateObj(template_name="notification", create_id=1)
    )
    assert template3.name == "notification"
    assert template3.template_text == template2.template_text
    await async_client.delete("/templates/1", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_product_template(async_client, token):
    qty = 10
    product_template = MockTemplateObj(template_name="product", create_id=2, mock_name="MockProduct")
    store = MockStore()
    # default product template
    template = await utils.templates.get_product_template(store, product_template, qty)
    assert template == f"Thanks for buying  x {qty}!\nIt'll ship shortly!\n"
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "product", "text": "store={{store}}|product={{product}}|quantity={{quantity}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.templates.get_product_template(store, product_template, qty)
    assert template == f"store={store}|product={product_template}|quantity={qty}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_store_template(async_client, token):
    shop = MockTemplateObj(template_name="shop", create_id=3, mock_name="MockShop")
    product = "my product"
    # default store template
    template = await utils.templates.get_store_template(shop, [product])
    assert template.startswith("Welcome to our shop")
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "shop", "text": "store={{store}}|products={{products}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.templates.get_store_template(shop, product)
    assert template == f"store={shop}|products={product}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_notification_template(async_client, token):
    invoice = "my invoice"
    notification = MockTemplateObj(template_name="notification", create_id=4, mock_name="MockNotification")
    # default notification template
    template = await utils.templates.get_notify_template(notification, invoice)
    assert template.strip() == "New order from"
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "notification", "text": "store={{store}}|invoice={{invoice}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.templates.get_notify_template(notification, invoice)
    assert template == f"store={notification}|invoice={invoice}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


def test_run_host(mocker):
    TEST_FILE = os.path.expanduser("~/test-output")
    content = f"touch {TEST_FILE}"
    # No valid ssh connection
    ok, error = utils.host.run_host(content)
    assert ok is False
    assert not os.path.exists(TEST_FILE)
    assert "Connection problem" in error
    assert "Name or service not known" in error
    assert utils.host.run_host_output(content, "good")["status"] == "error"
    # Same with key file
    settings.SSH_SETTINGS.key_file = "something"
    assert utils.host.run_host(content)[0] is False
    assert not os.path.exists(TEST_FILE)
    settings.SSH_SETTINGS.key_file = ""
    mocker.patch("paramiko.SSHClient.connect", return_value=True)
    mocker.patch(
        "paramiko.SSHClient.exec_command",
        side_effect=lambda command: subprocess.run(shlex.split(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    )
    ok, error = utils.host.run_host(content)
    assert ok is True
    assert error is None
    assert utils.host.run_host_output(content, "good") == {"status": "success", "message": "good"}
    time.sleep(1)  # wait for command to execute (non-blocking)
    assert os.path.exists(TEST_FILE)
    os.remove(TEST_FILE)  # Cleanup
