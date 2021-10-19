import os
import shutil

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from api import settings
from api.db import db
from main import get_app

# To separate setup fixtures from code testing helper fixtures
pytest_plugins = ["tests.fixtures.pytest.data"]


@pytest.fixture
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})


@pytest.fixture
def app():
    app = get_app()
    token = settings.settings_ctx.set(app.settings)
    yield app
    settings.settings_ctx.reset(token)


@pytest.fixture(autouse=True)
async def init_db(client, anyio_backend):
    await db.gino.create_all()
    yield
    await db.gino.drop_all()


@pytest.fixture
async def client(app, anyio_backend):
    async with LifespanManager(app), AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def service_dir():
    directory = "test-1"
    os.mkdir(directory)
    with open(f"{directory}/hostname", "w") as f:
        f.write("test.onion\n\n\n")
    yield directory
    shutil.rmtree(directory)


@pytest.fixture
def torrc(service_dir):
    filename = "torrc"
    with open(filename, "w") as f:
        f.write(
            """
HiddenServiceDir test-1
HiddenServicePort 80 127.0.0.1:80"""
        )
    yield filename
    os.remove(filename)


def deleting_file_base(filename):
    assert os.path.exists(filename)
    with open(filename) as f:
        contents = f.read().strip()
    yield filename
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(f"{contents}\n")


@pytest.fixture
def log_file():
    yield from deleting_file_base("tests/fixtures/log/bitcart20210821.log")
