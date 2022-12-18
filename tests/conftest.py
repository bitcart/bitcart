import os
import shutil

import anyio
import pytest
from async_asgi_testclient import TestClient as WSClient
from httpx import AsyncClient

from api import settings
from api.db import db
from api.settings import Settings
from main import get_app

# To separate setup fixtures from code testing helper fixtures
pytest_plugins = ["tests.fixtures.pytest.data"]
ANYIO_BACKEND_OPTIONS = {"use_uvloop": True}


@pytest.fixture
def anyio_backend():
    return ("asyncio", ANYIO_BACKEND_OPTIONS)


@pytest.fixture
def app():
    os.environ["BITCART_CRYPTOS"] = "btc"  # to avoid mixing environments
    os.environ["BTC_NETWORK"] = "testnet"
    app = get_app()
    token = settings.settings_ctx.set(app.settings)
    yield app
    settings.settings_ctx.reset(token)


async def setup_template_database():
    settings = Settings()
    db_name = settings.db_name
    template_db_name = f"{db_name}_template"
    settings.db_name = "postgres"
    async with settings.with_db():
        await db.status(f"DROP DATABASE IF EXISTS {template_db_name}")
        await db.status(f"CREATE DATABASE {template_db_name}")
    settings.db_name = template_db_name
    async with settings.with_db():
        await db.gino.create_all()


def pytest_sessionstart(session):
    if not hasattr(session.config, "workerinput"):
        anyio.run(setup_template_database, backend_options=ANYIO_BACKEND_OPTIONS)


@pytest.fixture(autouse=True)
async def init_db(request, app, anyio_backend):
    db_name = settings.settings.db_name
    template_db = f"{db_name}_template"
    xdist_suffix = getattr(request.config, "workerinput", {}).get("workerid")
    if xdist_suffix:
        db_name += f"_{xdist_suffix}"
    settings.settings.db_name = "postgres"
    async with settings.settings.with_db():
        await db.status(f"DROP DATABASE IF EXISTS {db_name}")
        await db.status(f"CREATE DATABASE {db_name} TEMPLATE {template_db}")
    settings.settings.db_name = db_name
    settings.settings.init_logging()
    await settings.settings.init()
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
