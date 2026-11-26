"""Real dependency probes. Nothing here reports a state it has not just measured."""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from Backend.App.Config import PROJECT_ROOT
from Database.PostgreSQL.Connection import pool_status

ALEMBIC_INI = PROJECT_ROOT / "Database" / "PostgreSQL" / "alembic.ini"


@lru_cache
def migration_heads() -> tuple[str, ...]:
    """Head revision(s) of the migration scripts shipped with this code."""
    script = ScriptDirectory.from_config(AlembicConfig(str(ALEMBIC_INI)))
    return tuple(sorted(script.get_heads()))


@dataclass
class DatabaseProbe:
    checked_at: datetime
    reachable: bool
    latency_ms: float | None = None
    server_version: str | None = None
    database_name: str | None = None
    current_revisions: tuple[str, ...] = ()
    head_revisions: tuple[str, ...] = field(default_factory=migration_heads)
    pool: dict[str, int | None] = field(default_factory=dict)
    error_type: str | None = None
    error_sqlstate: str | None = None

    @property
    def migrations_current(self) -> bool:
        return self.reachable and self.current_revisions == self.head_revisions


def probe_database(engine: Engine) -> DatabaseProbe:
    """Open a connection, run SELECT 1, and read server version and migration revision."""
    checked_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            server_version = connection.execute(text("SHOW server_version")).scalar_one()
            database_name = connection.execute(text("SELECT current_database()")).scalar_one()
            has_version_table = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            revisions: tuple[str, ...] = ()
            if has_version_table:
                rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                revisions = tuple(sorted(rows))
    except DBAPIError as exc:
        # Only the error class and SQLSTATE are kept: driver messages can include host and user names.
        return DatabaseProbe(
            checked_at=checked_at,
            reachable=False,
            pool=pool_status(engine),
            error_type=type(exc.orig).__name__ if exc.orig is not None else type(exc).__name__,
            error_sqlstate=getattr(exc.orig, "sqlstate", None),
        )
    except SQLAlchemyError as exc:
        return DatabaseProbe(checked_at=checked_at, reachable=False, pool=pool_status(engine), error_type=type(exc).__name__)

    return DatabaseProbe(
        checked_at=checked_at,
        reachable=True,
        latency_ms=latency_ms,
        server_version=server_version,
        database_name=database_name,
        current_revisions=revisions,
        pool=pool_status(engine),
    )
