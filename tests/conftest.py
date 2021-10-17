import os
import shutil

import anyio
import pytest
from async_asgi_testclient import TestClient as AsyncClient
from starlette.testclient import TestClient

from api.db import db
from main import get_app

# To separate setup fixtures from code testing helper fixtures
pytest_plugins = ["tests.fixtures.pytest.data"]


@pytest.fixture
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})


@pytest.fixture
def app():
    return get_app()


@pytest.fixture(autouse=True)
def init_db(client):
    anyio.run(db.gino.create_all)
    yield
    anyio.run(db.gino.drop_all)


@pytest.fixture
def client(app):
    with TestClient(app, backend_options={"use_uvloop": True}) as client:
        yield client


@pytest.fixture
async def async_client(app):
    async with AsyncClient(app) as client:
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
