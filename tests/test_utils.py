import asyncio
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

import pytest
from aioredis.client import PubSub
from bitcart.errors import BaseError as BitcartBaseError

from api import exceptions, schemes, settings, utils


def test_verify_password():
    p_hash = utils.authorization.get_password_hash("12345")
    assert isinstance(p_hash, str)
    assert utils.authorization.verify_password("12345", p_hash)


async def reader(chan):
    async for msg in utils.redis.listen_channel(chan):
        assert msg == {"hello": "world"}
        break


@pytest.mark.asyncio
async def test_auth_dependency():
    dep = utils.authorization.AuthDependency(enabled=False)
    assert not await dep(None, None)


@pytest.mark.asyncio
async def test_make_subscriber():
    sub = await utils.redis.make_subscriber("test")
    assert isinstance(sub, PubSub)
    await sub.subscribe("channel:test")
    utils.tasks.create_task(reader(sub), loop=settings.loop)
    assert await utils.redis.publish_message("test", {"hello": "world"}) == 1


@dataclass
class MockTemplateObj:
    template_name: str
    create_id: str = "1"
    mock_name: str = "MockTemplateObj"
    user_id: str = "1"
    id: str = "1"

    @property
    def templates(self):
        return {self.template_name: self.create_id}

    def __str__(self):
        return self.mock_name


@dataclass
class MockStore:
    user_id: str = "1"

    def __str__(self):
        return "MockStore"


@pytest.mark.asyncio
async def test_get_template(notification_template, async_client, token, user):
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
    template_id = resp.json()["id"]
    template2 = await utils.templates.get_template("templ", user_id=user["id"])
    assert template2.name == "templ"
    assert template2.template_text == "Hello {{var1}}!"
    assert template2.render() == "Hello !"
    assert template2.render(var1="world") == "Hello world!"
    template3 = await utils.templates.get_template(
        "notification", obj=MockTemplateObj(template_name="notification", create_id=template_id)
    )
    assert template3.name == "notification"
    assert template3.template_text == template2.template_text


@pytest.mark.asyncio
async def test_product_template(async_client, token, user):
    qty = 10
    product_template = MockTemplateObj(template_name="product", mock_name="MockProduct")
    store = MockStore(user_id=user["id"])
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
    template_id = resp.json()["id"]
    # Required for unique id
    product_template.create_id = template_id
    template = await utils.templates.get_product_template(store, product_template, qty)
    assert template == f"store={store}|product={product_template}|quantity={qty}"


@pytest.mark.asyncio
async def test_store_template(async_client, token, user):
    shop = MockTemplateObj(template_name="shop", mock_name="MockShop", user_id=user["id"])
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
    template_id = resp.json()["id"]
    shop.create_id = template_id
    template = await utils.templates.get_store_template(shop, product)
    assert template == f"store={shop}|products={product}"


@pytest.mark.asyncio
async def test_notification_template(async_client, token, user):
    invoice = "my invoice"
    notification = MockTemplateObj(template_name="notification", mock_name="MockNotification", user_id=user["id"])
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
    template_id = resp.json()["id"]
    notification.create_id = template_id
    template = await utils.templates.get_notify_template(notification, invoice)
    assert template == f"store={notification}|invoice={invoice}"


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


def test_versiontuple():
    assert utils.common.versiontuple("1.2.3") == (1, 2, 3)
    assert utils.common.versiontuple("0.6.0.0") == (0, 6, 0, 0)
    with pytest.raises(ValueError):
        utils.common.versiontuple("0.6.0.0dev")  # not supported for now


@pytest.mark.asyncio
async def test_custom_create_task(caplog):
    err_msg = "Test exception"

    async def task():
        raise Exception(err_msg)

    loop = asyncio.get_event_loop()
    utils.tasks.create_task(task(), loop=loop)
    await asyncio.sleep(1)
    assert err_msg in caplog.text
    caplog.clear()
    utils.tasks.create_task(task(), loop=loop).cancel()
    await asyncio.sleep(1)
    assert err_msg not in caplog.text


@pytest.mark.asyncio
async def test_no_exchange_rates_available(mocker, caplog, wallet):
    mocker.patch("bitcart.BTC.rate", side_effect=BitcartBaseError("No exchange rates available"))
    rate = await utils.wallets.get_rate(schemes.Wallet(**wallet), "USD")
    assert rate == Decimal(1)
    assert "Error fetching rates" in caplog.text


@pytest.mark.asyncio
async def test_broken_coin(mocker, caplog, wallet):
    mocker.patch("bitcart.BTC.balance", side_effect=BitcartBaseError("Coin broken"))
    success, balance = await utils.wallets.get_confirmed_wallet_balance(schemes.Wallet(**wallet))
    assert not success
    assert balance == Decimal(0)
    assert "Error getting wallet balance" in caplog.text


def test_search_query_parsing():
    q1 = utils.common.SearchQuery("text")
    assert q1.text == "text"
    assert q1.filters == {}
    q2 = utils.common.SearchQuery(
        'column:value column:value2 text column2:value2 text2 column3:other:value column2:value3 "column3:other:value"'
    )
    assert q2.text == "text text2 column3:other:value"
    assert q2.filters == {"column": ["value", "value2"], "column2": ["value2", "value3"], "column3": ["other:value"]}


def check_date(date, **kwargs):
    now = utils.time.now()
    assert now - date >= timedelta(**kwargs)


def test_search_query_parse_datetime():
    assert utils.common.SearchQuery("start_date:-1").parse_datetime("start_date") is None
    assert utils.common.SearchQuery("start_date:-testd").parse_datetime("start_date") is None
    check_date(utils.common.SearchQuery("start_date:-1d").parse_datetime("start_date"), days=1)
    check_date(utils.common.SearchQuery("end_date:-1d").parse_datetime("end_date"), days=1)
    check_date(utils.common.SearchQuery("start_date:-1h").parse_datetime("start_date"), hours=1)
    check_date(utils.common.SearchQuery("start_date:-1w").parse_datetime("start_date"), weeks=1)
    check_date(utils.common.SearchQuery("start_date:-1m").parse_datetime("start_date"), days=30)
    check_date(utils.common.SearchQuery("start_date:-1y").parse_datetime("start_date"), days=30 * 12)
    check_date(utils.common.SearchQuery("start_date:-150d").parse_datetime("start_date"), days=150)
