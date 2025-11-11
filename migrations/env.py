import asyncio
from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.schema import SchemaItem

from api.models import Model
from api.plugins import load_plugins
from api.settings import Settings
from api.sqltypes import PydanticJSON

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None and not config.get_main_option("no_logs"):
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

settings = Settings()
load_plugins(settings)

target_metadata = Model.metadata

config.set_main_option("sqlalchemy.url", settings.postgres_dsn.replace("%", "%%"))

del settings

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

plugin_name = config.get_main_option("plugin_name")
version_table = f"plugin_{plugin_name}_alembic_version" if plugin_name else "alembic_version"


def include_object(
    obj: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    if type_ == "table":
        if name is None:
            return False
        if name.startswith("app_"):
            return False
        if not plugin_name:
            return not name.startswith("plugin_")
        if getattr(obj, "PUBLIC", False):
            return True
        return name.startswith(f"plugin_{plugin_name}_")
    return True


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | Literal[False]:
    if isinstance(obj, PydanticJSON):
        return "postgresql.JSONB(astext_type=sa.Text())"
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        compare_type=True,
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        render_item=render_item,
        dialect_opts={"paramstyle": "named"},
        version_table=version_table,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        compare_type=True,
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        render_item=render_item,
        version_table=version_table,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    if not configuration:
        raise ValueError("No Alembic config found")

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
