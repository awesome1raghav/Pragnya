"""The single Alembic history applies to, and reverses on, a clean database."""

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text

from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Tests.conftest import alembic_config

pytestmark = pytest.mark.postgres


def _revisions(url: str) -> list[str]:
    engine = create_database_engine(url, EngineOptions(pooled=False))
    try:
        with engine.connect() as connection:
            if not connection.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar_one():
                return []
            return list(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    finally:
        engine.dispose()


def test_history_is_linear_with_one_head(migrated_database):
    script = ScriptDirectory.from_config(alembic_config(migrated_database[1]))
    assert script.get_heads() == ["0005"]
    assert [rev.revision for rev in script.walk_revisions()] == ["0005", "0004", "0003", "0002", "0001"]


def test_upgrade_and_downgrade_on_clean_database(database_factory):
    _, url = database_factory()
    config = alembic_config(url)
    assert _revisions(url) == []

    command.upgrade(config, "head")
    assert _revisions(url) == ["0005"]

    command.downgrade(config, "base")
    assert _revisions(url) == []

    command.upgrade(config, "head")
    assert _revisions(url) == ["0005"]
