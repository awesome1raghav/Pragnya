"""Engine creation and connection-pool inspection for PostgreSQL (psycopg 3 driver)."""

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool, QueuePool


@dataclass(frozen=True)
class EngineOptions:
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout_seconds: float = 5.0
    connect_timeout_seconds: int = 3
    application_name: str = "nextron-api"
    pooled: bool = True


def create_database_engine(url: str, options: EngineOptions | None = None) -> Engine:
    """Create an engine. No connection is opened until first use.

    `pooled=False` (migrations, one-off scripts) opens a fresh connection per checkout.
    """
    options = options or EngineOptions()
    connect_args = {
        "connect_timeout": options.connect_timeout_seconds,
        "application_name": options.application_name,
        "options": "-c timezone=UTC",
    }
    if not options.pooled:
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    return create_engine(
        url,
        pool_size=options.pool_size,
        max_overflow=options.max_overflow,
        pool_timeout=options.pool_timeout_seconds,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def pool_status(engine: Engine) -> dict[str, int | None]:
    """Counts from SQLAlchemy's QueuePool for this process (not server-wide connections)."""
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        return {"checked_out": None, "idle": None, "overflow": None, "maximum": None}
    return {
        "checked_out": pool.checkedout(),
        "idle": pool.checkedin(),
        "overflow": max(pool.overflow(), 0),
        "maximum": pool.size() + pool._max_overflow,  # noqa: SLF001 — no public accessor exists
    }
