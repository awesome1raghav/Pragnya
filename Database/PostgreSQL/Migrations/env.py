"""Alembic environment for the single NEXTRON PostgreSQL history."""

from logging.config import fileConfig

from alembic import context

import Database.PostgreSQL.Models  # noqa: F401 — registers every table on Base.metadata
from Database.PostgreSQL.Base import Base
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    from Backend.App.Config import get_settings

    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_database_engine(
        _database_url(), EngineOptions(pooled=False, application_name="nextron-migrations")
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
