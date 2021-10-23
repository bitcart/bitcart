import os
import shutil

import pytest
from async_asgi_testclient import TestClient as WSClient
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
async def init_db(request, app, anyio_backend):
    xdist_suffix = getattr(request.config, "workerinput", {}).get("workerid")
    db_name = f"{settings.settings.db_name}"
    if xdist_suffix:
        db_name += f"_{xdist_suffix}"
    settings.settings.db_name = "postgres"
    async with settings.settings.with_db():
        async with db.acquire() as conn:
            await conn.status(f"DROP DATABASE IF EXISTS {db_name}")
            await conn.status(f"CREATE DATABASE {db_name}")
    settings.settings.db_name = db_name
    await settings.settings.init()
    await db.gino.create_all()
    yield


@pytest.fixture
async def client(app, anyio_backend):
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# TODO: remove when httpx supports websockets
@pytest.fixture
async def ws_client(app, anyio_backend):
    client = WSClient(app)
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
    yield from deleting_file_base("tests/fixtures/logs/bitcart20210821.log")
