import functools
import os
import subprocess
import tempfile
import time
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Iterator
from decimal import Decimal
from typing import Any, NewType, cast
from unittest.mock import AsyncMock

import email_validator
import pyotp
import pytest
import pytest_mock
from dishka import Provider, Scope, decorate, from_context, provide
from fastapi import FastAPI
from filelock import FileLock
from httpx import AsyncClient
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import text

from api.bootstrap import get_app
from api.db import AsyncEngine, create_async_engine
from api.ioc import build_container, setup_dishka
from api.logging import configure as configure_logging
from api.models import Model
from api.plugins import PluginObjects
from api.services.coins import CoinService
from api.services.exchange_rate import ExchangeRateService
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings
from tests.helper import make_client

pytest_plugins = ["tests.fixtures.pytest.data", "tests.fixtures.pytest.agent", "tests.fixtures.pytest.coingecko"]

ANYIO_BACKEND_OPTIONS = {"use_uvloop": True}

email_validator.TEST_ENVIRONMENT = True


@pytest.fixture(scope="session")
def anyio_backend() -> tuple[str, dict[str, Any]]:
    return ("asyncio", ANYIO_BACKEND_OPTIONS)


def get_db_url(settings: Settings, worker_id: str) -> str:
    if worker_id != "master":
        return f"{settings.DB_DATABASE}_{worker_id}"
    return settings.DB_DATABASE


async def initialize_test_database(settings: Settings, worker_id: str) -> None:
    template_db_name = f"{settings.DB_DATABASE}_template"
    database_url = settings.build_postgres_dsn(db_name=template_db_name)
    engine = create_async_engine(settings, "test", dsn=settings.build_postgres_dsn(db_name="postgres"))
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"DROP DATABASE IF EXISTS {template_db_name}"))
        await conn.execute(text(f"CREATE DATABASE {template_db_name}"))
    await engine.dispose()
    engine = create_async_engine(settings, "test", dsn=database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_database_fixture(
    settings: Settings,
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    if worker_id == "master":
        await initialize_test_database(settings, worker_id)
        return
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            pass
        else:
            await initialize_test_database(settings, worker_id)
            fn.write_text("DONE")


WorkerId = NewType("WorkerId", str)


class TestingProvider(Provider):
    worker_id = from_context(provides=WorkerId, scope=Scope.APP)

    @provide(scope=Scope.RUNTIME)
    def get_plugin_clases(self) -> PluginObjects:
        return cast(PluginObjects, {})

    @provide(scope=Scope.RUNTIME)
    def get_password_context(self) -> PasswordHash:
        return PasswordHash((BcryptHasher(rounds=4),))

    @provide(scope=Scope.APP)
    async def get_async_engine(self, settings: Settings, worker_id: WorkerId) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(
            settings, "test", dsn=settings.build_postgres_dsn(db_name=get_db_url(settings, worker_id))
        )
        yield engine
        await engine.dispose()

    # TODO: if we make fake redis work with functional tests of websockets, we can no longer require redis for tests
    # @provide(scope=Scope.RUNTIME)
    # async def get_redis(self) -> AsyncIterator[Redis]:
    #     async with FakeAsyncRedis(decode_responses=True) as redis:
    #         yield redis

    @decorate
    async def get_exchange_rate_service(
        self,
        service: ExchangeRateService,
    ) -> AsyncIterator[ExchangeRateService]:
        await service.init()
        yield service


@pytest.fixture(autouse=True)
async def configure_dishka_test_session(app: FastAPI, worker_id: str, settings: Settings) -> AsyncIterator[None]:
    db_name = get_db_url(settings, worker_id)
    template_db = f"{settings.DB_DATABASE}_template"
    engine = create_async_engine(settings, "test", dsn=settings.build_postgres_dsn(db_name="postgres"))
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        await conn.execute(text(f"CREATE DATABASE {db_name} TEMPLATE {template_db}"))
    await engine.dispose()
    async with app.state.dishka_container(scope=Scope.APP, context={WorkerId: worker_id}) as container:
        original_container = app.state.dishka_container
        app.state.dishka_container = container
        yield
    app.state.dishka_container = original_container


@pytest.fixture(scope="session")
def renderer_socket(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = tmp_path_factory.getbasetemp().parent
    with FileLock(str(root / "renderer-build.lock")):
        subprocess.run(["cargo", "build", "--quiet", "--manifest-path", "renderer/Cargo.toml"], check=True)
    # unix socket paths are limited to about 100 characters, which pytest's nested temp directories can exceed
    with tempfile.TemporaryDirectory(prefix="renderer-", dir="/tmp") as directory:
        socket_path = f"{directory}/renderer.sock"
        process = subprocess.Popen(
            ["renderer/target/debug/bitcart-renderer"],
            env={**os.environ, "RENDERER_SOCKET": socket_path, "RENDERER_WORKERS": "1"},
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while not os.path.exists(socket_path):
            if time.monotonic() > deadline or process.poll() is not None:
                process.kill()
                raise RuntimeError("Template renderer did not start")
            time.sleep(0.01)
        yield socket_path
        process.terminate()
        process.wait()


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory, renderer_socket: str) -> Settings:
    os.environ["BITCART_ENV"] = "testing"
    os.environ["BITCART_CRYPTOS"] = "btc"
    os.environ["BTC_NETWORK"] = "testnet"
    os.environ["BITCART_DATADIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ["RENDERER_SOCKET"] = renderer_socket
    os.environ["RENDERER_TIMEOUT"] = "5"
    return Settings()


@pytest.fixture(scope="session")
def app(settings: Settings) -> Generator[FastAPI]:
    container = build_container(
        settings, extra_providers=(TestingProvider(),), include_plugins=False, start_scope=Scope.RUNTIME
    )
    app = get_app(settings)
    setup_dishka(container=container, app=app)
    configure_logging(settings=settings)
    yield app


@pytest.fixture
async def client(app: FastAPI, anyio_backend: tuple[str, dict[str, Any]]) -> AsyncGenerator[AsyncClient]:
    async with make_client(app) as client:
        yield client


@pytest.fixture
def service_dir() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as directory:
        with open(f"{directory}/hostname", "w") as f:
            f.write("test.onion\n\n\n")
        yield directory


@pytest.fixture
def torrc(service_dir: str) -> str:
    filename = f"{service_dir}/torrc"
    with open(filename, "w") as f:
        f.write(
            f"""
HiddenServiceDir {service_dir}
HiddenServicePort 80 127.0.0.1:80"""
        )
    return filename


def deleting_file_base(filename: str) -> Generator[str, None, None]:
    assert os.path.exists(filename)
    with open(filename) as f:
        contents = f.read().strip()
    yield filename
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(f"{contents}\n")


@pytest.fixture
def log_file() -> Generator[str, None, None]:
    yield from deleting_file_base("tests/fixtures/logs/bitcart20210821.log")


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        (
            "exchange_rates: mark test as requiring exchange rates mocking. For now in all tests it is mocked, you can use"
            " cryptos param to specify which cryptos to enable"
        ),
    )


@pytest.fixture
async def coin_service(app: FastAPI) -> CoinService:
    return await app.state.dishka_container.get(CoinService)


@pytest.fixture
async def plugin_registry(app: FastAPI) -> PluginRegistry:
    return await app.state.dishka_container.get(PluginRegistry)


@pytest.fixture(autouse=True)
def exchange_rates_cryptos(
    request: pytest.FixtureRequest,
    mocker: pytest_mock.MockerFixture,
    coin_service: CoinService,
    anyio_backend: tuple[str, dict[str, Any]],
) -> None:
    marker = request.node.get_closest_marker("exchange_rates")
    cryptos = marker.kwargs.get("cryptos") if marker else None
    if cryptos is not None:
        mocker.patch.object(coin_service, "_cryptos", cryptos)


# TODO: remove and port to app itself once we added rate limits to TOTP
@pytest.fixture(autouse=True)
def totp_valid_window(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch.object(pyotp.TOTP, "verify", functools.partialmethod(pyotp.TOTP.verify, valid_window=1))


@pytest.fixture
def mock_btc_balance(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch(
        "bitcart.BTC.balance",
        new=AsyncMock(
            return_value={
                "confirmed": Decimal("1.5"),
                "unconfirmed": Decimal("0"),
                "unmatured": Decimal("0"),
                "lightning": Decimal("0"),
            }
        ),
    )
