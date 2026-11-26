"""System status endpoints with real probes: /system/database, /system/storage, /system/modules, /system/workers."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Orchestration import ModuleCatalog
from Backend.App.Orchestration.TMir import DependencyRegistry as Registry
from Backend.App.Dependencies import get_db_session, get_engine
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Services.HealthService import probe_database
from Database.PostgreSQL.Models import WorkerProcess

router = APIRouter(prefix="/system", tags=["System"])


class MigrationState(BaseModel):
    current: list[str]
    head: list[str]
    up_to_date: bool


class ConnectionPool(BaseModel):
    """This API process's SQLAlchemy pool, not server-wide connection counts."""

    checked_out: int | None
    idle: int | None
    overflow: int | None
    maximum: int | None


class DatabaseStatus(BaseModel):
    status: Literal["HEALTHY", "DEGRADED"]
    database: Literal["postgresql"] = "postgresql"
    server_version: str
    database_name: str
    latency_ms: float
    migrations: MigrationState
    connection_pool: ConnectionPool
    checked_at: datetime
    last_successful_check: datetime


class ModuleInfo(BaseModel):
    module_id: str
    number: int
    name: str
    group: str
    executed_by: Literal["DOMAIN_SERVICE", "T-MIR", "SOURCE_JOB", "HUMAN_REVIEW", "REPORT_JOB"]
    status: Literal["IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"]
    upstream: list[str]
    downstream: list[str]
    capabilities: list[str]
    endpoints: list[str]
    note: str | None


class ModuleEdge(BaseModel):
    upstream: str
    downstream: str
    kind: Literal["REQUIRED", "CONDITIONAL", "OPTIONAL"]
    reason: str


class ModuleCatalogue(BaseModel):
    source: str
    groups: list[str]
    modules: list[ModuleInfo]
    edges: list[ModuleEdge]
    tmir: dict
    execution_tracking: Literal["PERSISTED"] = "PERSISTED"  # executions, results and findings are stored per run


@router.get("/modules", response_model=SuccessEnvelope[ModuleCatalogue], summary="Investigation modules and connectivity")
def modules() -> SuccessEnvelope[ModuleCatalogue]:
    items = [
        ModuleInfo(
            module_id=m.module_id, number=m.number, name=m.name, group=m.group, executed_by=m.executed_by, status=m.status,
            upstream=ModuleCatalog.upstream(m.module_id), downstream=ModuleCatalog.downstream(m.module_id),
            capabilities=list(m.capabilities), endpoints=list(m.endpoints), note=m.note,
        )
        for m in ModuleCatalog.MODULES
    ]
    data = ModuleCatalogue(
        source="Canonical module connectivity flowchart (A1)",
        groups=list(ModuleCatalog.GROUPS),
        modules=items,
        edges=[ModuleEdge(upstream=e.upstream, downstream=e.downstream, kind=e.kind.value, reason=e.reason) for e in Registry.EDGES],
        tmir={"status": ModuleCatalog.TMIR_STATUS, "coordinates": list(ModuleCatalog.TMIR_COORDINATED)},
    )
    return envelope(data, "Module catalogue retrieved successfully")


class StorageStatus(BaseModel):
    status: Literal["HEALTHY"] = "HEALTHY"
    backend: Literal["local-filesystem"] = "local-filesystem"
    writable: bool
    free_bytes: int | None
    max_upload_bytes: int
    checked_at: datetime


@router.get(
    "/storage",
    response_model=SuccessEnvelope[StorageStatus],
    responses={503: {"model": ErrorEnvelope, "description": "Evidence storage is not writable"}},
    summary="Evidence storage status",
)
def storage_status(request: Request) -> SuccessEnvelope[StorageStatus]:
    checked_at = datetime.now(timezone.utc)
    health = request.app.state.storage.health()
    if not health.writable:
        raise NextronError(
            503,
            ErrorCode.STORAGE_UNAVAILABLE,
            "Evidence storage is not writable",
            {"available": health.available, "error_type": health.error, "checked_at": checked_at.isoformat()},
        )
    data = StorageStatus(
        writable=True, free_bytes=health.free_bytes, max_upload_bytes=request.app.state.settings.MAX_UPLOAD_SIZE_BYTES, checked_at=checked_at
    )
    return envelope(data, "Evidence storage is writable")


@router.get(
    "/database",
    response_model=SuccessEnvelope[DatabaseStatus],
    responses={503: {"model": ErrorEnvelope, "description": "PostgreSQL is unreachable"}},
    summary="PostgreSQL status",
)
def database_status(request: Request, engine: Engine = Depends(get_engine)) -> SuccessEnvelope[DatabaseStatus]:
    probe = probe_database(engine)
    if not probe.reachable:
        last = request.app.state.last_database_success
        raise NextronError(
            503,
            ErrorCode.DATABASE_UNAVAILABLE,
            "PostgreSQL is unreachable",
            {
                "checked_at": probe.checked_at.isoformat(),
                "last_successful_check": last.isoformat() if last else None,
                "error_type": probe.error_type,
                "sqlstate": probe.error_sqlstate,
            },
        )

    request.app.state.last_database_success = probe.checked_at
    data = DatabaseStatus(
        status="HEALTHY" if probe.migrations_current else "DEGRADED",
        server_version=probe.server_version,
        database_name=probe.database_name,
        latency_ms=probe.latency_ms,
        migrations=MigrationState(
            current=list(probe.current_revisions),
            head=list(probe.head_revisions),
            up_to_date=probe.migrations_current,
        ),
        connection_pool=ConnectionPool(**probe.pool),
        checked_at=probe.checked_at,
        last_successful_check=probe.checked_at,
    )
    message = "PostgreSQL is reachable" if probe.migrations_current else "PostgreSQL is reachable but not migrated to head"
    return envelope(data, message)


class WorkerInfo(BaseModel):
    worker_id: str
    hostname: str
    pid: int
    version: str
    state: Literal["RUNNING", "STOPPED"]
    alive: bool  # RUNNING and heartbeating within the lease window
    current_job_id: str | None
    started_at: datetime
    heartbeat_at: datetime
    stopped_at: datetime | None


class WorkersStatus(BaseModel):
    alive: int
    workers: list[WorkerInfo]
    lease_seconds: int
    checked_at: datetime


@router.get("/workers", response_model=SuccessEnvelope[WorkersStatus], summary="Registered worker processes and their heartbeats")
def workers(request: Request, session: Session = Depends(get_db_session)) -> SuccessEnvelope[WorkersStatus]:
    settings = request.app.state.settings
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=max(settings.JOB_LEASE_SECONDS, 3 * settings.JOB_HEARTBEAT_SECONDS, 3 * settings.WORKER_POLL_SECONDS))
    rows = session.scalars(select(WorkerProcess).order_by(WorkerProcess.heartbeat_at.desc()).limit(50)).all()
    items = [
        WorkerInfo(worker_id=w.worker_id, hostname=w.hostname, pid=w.pid, version=w.version, state=w.state,
                   alive=w.state == "RUNNING" and now - w.heartbeat_at <= window,
                   current_job_id=str(w.current_job_id) if w.current_job_id else None, started_at=w.started_at,
                   heartbeat_at=w.heartbeat_at, stopped_at=w.stopped_at)
        for w in rows
    ]
    alive = sum(1 for w in items if w.alive)
    message = f"{alive} worker{'s' if alive != 1 else ''} running" if alive else "No worker is running: queued jobs will wait"
    return envelope(WorkersStatus(alive=alive, workers=items, lease_seconds=settings.JOB_LEASE_SECONDS, checked_at=now), message)


class ProjectionStatus(BaseModel):
    consumer: str
    configured: bool
    reachable: bool | None
    checkpoint: int
    latest_sequence: int
    lag_events: int
    snapshots_pending: bool
    nodes: int | None
    relationships: int | None
    server_version: str | None
    error: str | None


@router.get("/projections", response_model=SuccessEnvelope[list[ProjectionStatus]],
            summary="Read projections of PostgreSQL (Neo4j graph): checkpoint, lag and reachability")
def projections(request: Request, session: Session = Depends(get_db_session)) -> SuccessEnvelope[list[ProjectionStatus]]:
    return envelope([ProjectionStatus(**request.app.state.graph.status(session))], "Projection status retrieved successfully")


@router.post("/projections/neo4j/rebuild", response_model=SuccessEnvelope[dict],
             responses={503: {"model": ErrorEnvelope, "description": "PROJECTION_UNAVAILABLE"}},
             summary="Rebuild the Neo4j graph from PostgreSQL (every case's latest snapshot)")
def rebuild_graph(request: Request) -> SuccessEnvelope[dict]:
    graph = request.app.state.graph
    if not graph.configured:
        raise NextronError(503, ErrorCode.PROJECTION_UNAVAILABLE, "NEO4J_URI is not set; the projection is disabled")
    try:
        result = graph.rebuild()
    except Exception as exc:  # noqa: BLE001
        graph.close()
        raise NextronError(503, ErrorCode.PROJECTION_UNAVAILABLE, "Neo4j is unreachable", {"error_type": type(exc).__name__}) from exc
    return envelope(result, f"Rebuilt the graph for {result['cases_projected']} cases")


@router.get("/config", response_model=SuccessEnvelope[dict], summary="Non-secret server configuration (read-only)")
def system_config(request: Request) -> SuccessEnvelope[dict]:
    """What the server is configured to do. Credentials, database addresses and paths are never included."""
    st = request.app.state.settings
    return envelope({
        "environment": st.ENVIRONMENT, "version": st.APP_VERSION, "operator": st.OPERATOR_NAME,
        "uploads": {"max_bytes": st.MAX_UPLOAD_SIZE_BYTES, "auto_analyze_default": st.AUTO_ANALYZE_ON_UPLOAD},
        "jobs": {"lease_seconds": st.JOB_LEASE_SECONDS, "max_attempts": st.JOB_MAX_ATTEMPTS, "job_timeout_seconds": st.JOB_TIMEOUT_SECONDS,
                 "module_timeout_seconds": st.MODULE_TIMEOUT_SECONDS},
        "detectors": {"enabled": st.DETECTORS_ENABLED, "image": st.IMAGE_DETECTOR or None, "speech": st.SPEECH_DETECTOR or None,
                      "timeout_seconds": st.DETECTOR_TIMEOUT_SECONDS},
        "projections": {"neo4j": bool(st.NEO4J_URI), "qdrant": bool(st.QDRANT_URL)},
        "web_visual_search": {"enabled": st.WEB_VISUAL_SEARCH_ENABLED, "key_configured": bool(getattr(st.SERPAPI_API_KEY, "get_secret_value", lambda: st.SERPAPI_API_KEY)())},
        "cors_origins": list(st.CORS_ORIGINS),
    }, "Configuration retrieved successfully")
