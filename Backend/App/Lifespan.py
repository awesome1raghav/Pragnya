"""Application startup and shutdown.

The engine is created at startup but connects lazily, so the API still starts (and
/health still answers) when PostgreSQL is down; /health/ready then reports the outage.
The outbox dispatcher runs as one background task for the life of the process.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from Backend.App.Projections.Neo4jGraph import Neo4jGraph
from Backend.App.Realtime.Dispatcher import Dispatcher
from Backend.App.Realtime.Hub import Hub
from Backend.App.Storage.LocalStorage import LocalStorage
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    app.state.engine = create_database_engine(
        settings.DATABASE_URL,
        EngineOptions(
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout_seconds=settings.DATABASE_POOL_TIMEOUT_SECONDS,
            connect_timeout_seconds=settings.DATABASE_CONNECT_TIMEOUT_SECONDS,
        ),
    )
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.storage = LocalStorage(settings.STORAGE_ROOT)
    try:
        app.state.storage.ensure_layout()
    except OSError:
        pass  # reported by /health/ready and /system/storage rather than blocking startup
    app.state.last_database_success = None
    app.state.graph = Neo4jGraph(settings, app.state.session_factory)  # status and rebuild; the worker keeps it current
    app.state.hub = Hub()
    app.state.dispatcher = Dispatcher(app.state.session_factory, app.state.hub, poll_seconds=settings.OUTBOX_POLL_SECONDS,
                                    operator=settings.OPERATOR_NAME)
    dispatch_task = asyncio.create_task(app.state.dispatcher.run(), name="outbox-dispatcher")
    try:
        yield
    finally:
        dispatch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await dispatch_task
        app.state.graph.close()
        app.state.engine.dispose()
