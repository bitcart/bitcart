import os
import tempfile

import anyio
import pytest
from httpx import AsyncClient
from httpx_ws.transport import ASGIWebSocketTransport

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
    await settings.settings.init()
    return


@pytest.fixture
async def client(app, anyio_backend):
    async with AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest.fixture
def service_dir():
    with tempfile.TemporaryDirectory() as directory:
        with open(f"{directory}/hostname", "w") as f:
            f.write("test.onion\n\n\n")
        yield directory


@pytest.fixture
def torrc(service_dir):
    filename = f"{service_dir}/torrc"
    with open(filename, "w") as f:
        f.write(
            f"""
HiddenServiceDir {service_dir}
HiddenServicePort 80 127.0.0.1:80"""
        )
    return filename


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


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        (
            "exchange_rates: mark test as requiring exchange rates mocking. For now in all tests it is mocked, you can use"
            " cryptos param to specify which cryptos to enable"
        ),
    )


async def mock_fetch_delayed(*args, **kwargs):
    req_url = args[1]
    if "simple/supported_vs_currencies" in req_url:
        return ["btc", "usd", "eur"]
    if "coins/list" in req_url:
        coins = []
        for crypto in settings.settings.cryptos:
            coins.append({"id": crypto, "symbol": crypto, "name": crypto.upper()})
        return coins
    if "simple/price" in req_url:
        return {crypto: {"usd": 50000, "eur": 45000} for crypto in settings.settings.cryptos}
    return {}


@pytest.fixture(autouse=True)
def mock_coingecko_api(request, mocker):
    marker = request.node.get_closest_marker("exchange_rates")
    cryptos = marker.kwargs.get("cryptos") if marker else None
    if cryptos is not None:
        mocker.patch.object(settings.settings, "cryptos", cryptos)
    mocker.patch("api.ext.exchanges.coingecko.fetch_delayed", side_effect=mock_fetch_delayed)
