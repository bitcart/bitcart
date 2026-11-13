import asyncio
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, inspect, text

from api.db import create_async_engine
from api.settings import Settings
from tests.conftest import execute_as_admin, get_db_url

pytestmark = pytest.mark.anyio

LIST_FUNCTIONS = text(
    "SELECT p.oid::regprocedure::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'"
)


def by_name(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {item["name"]: item for item in items}


def read_schema(conn: Connection) -> dict[str, Any]:
    inspector = inspect(conn)
    return {
        "functions": sorted(conn.execute(LIST_FUNCTIONS).scalars()),
        "sequences": sorted(inspector.get_sequence_names()),
        "tables": {
            table: {
                "columns": {
                    column["name"]: {**column, "type": str(column["type"])} for column in inspector.get_columns(table)
                },
                "primary_key": inspector.get_pk_constraint(table),
                "indexes": by_name(inspector.get_indexes(table)),
                "unique_constraints": by_name(inspector.get_unique_constraints(table)),
                "foreign_keys": by_name(inspector.get_foreign_keys(table)),
                "check_constraints": by_name(inspector.get_check_constraints(table)),
            }
            for table in inspector.get_table_names()
            if table != "alembic_version"
        },
    }


async def load_schema(settings: Settings, database: str) -> dict[str, Any]:
    engine = create_async_engine(settings, "test", dsn=settings.build_postgres_dsn(db_name=database))
    async with engine.connect() as conn:
        schema = await conn.run_sync(read_schema)
    await engine.dispose()
    return schema


def find_differences(migrated: Any, models: Any, path: str = "") -> Iterator[str]:
    if isinstance(migrated, dict) and isinstance(models, dict):
        for key in sorted(migrated.keys() | models.keys()):
            yield from find_differences(migrated.get(key), models.get(key), f"{path}/{key}")
    elif migrated != models:
        yield f"{path}: migrated={migrated} models={models}"


async def assert_matches_models(settings: Settings, worker_id: str, database: str) -> None:
    migrated = await load_schema(settings, database)
    models = await load_schema(settings, get_db_url(settings, worker_id))
    differences = list(find_differences(migrated, models))
    assert not differences, "\n".join(differences)


@pytest.fixture
def alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("no_logs", "true")
    return config


@pytest.fixture
async def migrated_database(
    settings: Settings, worker_id: str, monkeypatch: pytest.MonkeyPatch, alembic_config: Config
) -> AsyncIterator[str]:
    alembic_database = f"{get_db_url(settings, worker_id)}_migrated"
    database = Settings(DB_DATABASE=alembic_database).DB_DATABASE
    await execute_as_admin(settings, f"DROP DATABASE IF EXISTS {database}")
    await execute_as_admin(settings, f"CREATE DATABASE {database}")
    monkeypatch.setenv("DB_DATABASE", alembic_database)
    try:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        yield database
    finally:
        await execute_as_admin(settings, f"DROP DATABASE IF EXISTS {database}")


async def test_migrations_match_models(settings: Settings, worker_id: str, migrated_database: str) -> None:
    await assert_matches_models(settings, worker_id, migrated_database)


async def test_migrations_downgrade_to_empty_and_upgrade_again(
    settings: Settings, worker_id: str, migrated_database: str, alembic_config: Config
) -> None:
    await asyncio.to_thread(command.downgrade, alembic_config, "base")
    assert await load_schema(settings, migrated_database) == {"functions": [], "sequences": [], "tables": {}}
    await asyncio.to_thread(command.upgrade, alembic_config, "head")
    await assert_matches_models(settings, worker_id, migrated_database)
