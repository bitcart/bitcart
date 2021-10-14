import asyncio
import os
import shutil

import pytest
from async_asgi_testclient import TestClient as AsyncClient
from starlette.testclient import TestClient

from api import models
from api.db import db
from main import app

# To separate setup fixtures from code testing helper fixtures
pytest_plugins = ["tests.fixtures.pytest.data"]


@pytest.fixture(scope="session", autouse=True)
async def init_db():
    await db.gino.create_all()
    yield
    await db.gino.drop_all()


# We re-create database per each test to make tests independent of each others' state
@pytest.fixture(autouse=True)
async def cleanup_db():
    async with db.acquire() as conn:
        async with conn.transaction():
            for table in reversed(models.db.sorted_tables):
                await conn.status(table.delete())


@pytest.fixture(scope="session")
def event_loop():
    yield asyncio.get_event_loop_policy().get_event_loop()


@pytest.fixture(scope="session", autouse=True)
def client(event_loop):
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client(event_loop):
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
