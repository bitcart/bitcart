import tempfile
from dataclasses import dataclass

import aioredis
import fastapi
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


@dataclass
class MockTemplateObj:
    template_name: str
    create_id: int
    mock_name: str = "MockTemplateObj"
    user_id: int = 1

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
    template2 = await utils.get_template("templ", user_id=1)
    assert template2.name == "templ"
    assert template2.template_text == "Hello {{var1}}!"
    assert template2.render() == "Hello !"
    assert template2.render(var1="world") == "Hello world!"
    template3 = await utils.get_template("notification", obj=MockTemplateObj(template_name="notification", create_id=1))
    assert template3.name == "notification"
    assert template3.template_text == template2.template_text
    await async_client.delete("/templates/1", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_product_template(async_client, token):
    qty = 10
    product_template = MockTemplateObj(template_name="product", create_id=2, mock_name="MockProduct")
    store = MockStore()
    # default product template
    template = await utils.get_product_template(store, product_template, qty)
    assert template == f"Thanks for buying  x {qty}!\nIt'll ship shortly!\n"
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "product", "text": "store={{store}}|product={{product}}|quantity={{quantity}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.get_product_template(store, product_template, qty)
    assert template == f"store={store}|product={product_template}|quantity={qty}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_store_template(async_client, token):
    shop = MockTemplateObj(template_name="shop", create_id=3, mock_name="MockShop")
    product = "my product"
    # default store template
    template = await utils.get_store_template(shop, [product])
    assert template.startswith("Welcome to our shop")
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "shop", "text": "store={{store}}|products={{products}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.get_store_template(shop, product)
    assert template == f"store={shop}|products={product}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.asyncio
async def test_notification_template(async_client, token):
    invoice = "my invoice"
    notification = MockTemplateObj(template_name="notification", create_id=4, mock_name="MockNotification")
    # default notification template
    template = await utils.get_notify_template(notification, invoice)
    assert template.strip() == "New order from"
    # custom template
    resp = await async_client.post(
        "/templates",
        json={"name": "notification", "text": "store={{store}}|invoice={{invoice}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template = await utils.get_notify_template(notification, invoice)
    assert template == f"store={notification}|invoice={invoice}"
    await async_client.delete(f"/templates/{resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})  # cleanup


@pytest.mark.parametrize("exist", [True, False])
def test_run_host(exist):
    content = "echo hello"
    if exist:
        with tempfile.NamedTemporaryFile() as temp:
            utils.run_host(content, target_file=temp.name)
            with open(temp.name, "r") as f:
                assert f.read().strip() == content
    else:
        with pytest.raises(fastapi.HTTPException):
            utils.run_host(content)
