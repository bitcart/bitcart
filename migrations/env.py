from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.models import db
from api.settings import Settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if not config.get_main_option("no_logs"):
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = None


settings = Settings()
settings.init_logging(worker=False)
settings.load_plugins()
CONNECTION_STR = settings.connection_str
target_metadata = db

del settings  # to ensure connections are closed in time

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

plugin_name = config.get_main_option("plugin_name")
version_table = f"plugin_{plugin_name}_alembic_version" if plugin_name else "alembic_version"


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        if name.startswith("app_"):
            return False
        if not plugin_name:
            return not name.startswith("plugin_")
        if getattr(obj, "PUBLIC", False):
            return True
        return name.startswith(f"plugin_{plugin_name}_")
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    alembic_config = config.get_section(config.config_ini_section)
    alembic_config["sqlalchemy.url"] = CONNECTION_STR

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        compare_type=True,
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        dialect_opts={"paramstyle": "named"},
        version_table=version_table,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    alembic_config = config.get_section(config.config_ini_section)
    alembic_config["sqlalchemy.url"] = CONNECTION_STR

    connectable = engine_from_config(alembic_config, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            compare_type=True,
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table=version_table,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
