import aioredis
import pytest

from api import settings, utils


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
async def test_make_subscriber():
    sub, chan = await utils.make_subscriber("test")
    assert sub is not None
    assert chan is not None
    assert isinstance(sub, aioredis.Redis)
    assert isinstance(chan, aioredis.Channel)
    await sub.subscribe("channel:test")
    settings.loop.create_task(reader(chan))
    assert await utils.publish_message("test", {"hello": "world"}) == 1
