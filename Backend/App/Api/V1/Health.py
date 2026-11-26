"""Liveness and readiness.

GET /health        — the API process is running. Touches no dependency.
GET /health/ready  — required dependencies are usable: PostgreSQL reachable and migrated to head.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import Engine

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_engine, get_settings_dependency
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Services.HealthService import probe_database

router = APIRouter(prefix="/health", tags=["Health"])


class LivenessData(BaseModel):
    status: Literal["ALIVE"] = "ALIVE"
    service: str
    version: str
    environment: str


class DatabaseCheck(BaseModel):
    status: Literal["PASS", "FAIL"]
    reachable: bool
    migrations_current: bool
    latency_ms: float | None
    reason: str | None = None


class StorageCheck(BaseModel):
    status: Literal["PASS", "FAIL"]
    writable: bool
    reason: str | None = None


class ReadinessChecks(BaseModel):
    database: DatabaseCheck
    storage: StorageCheck


class ReadinessData(BaseModel):
    status: Literal["READY"] = "READY"
    checks: ReadinessChecks


@router.get("", response_model=SuccessEnvelope[LivenessData], summary="Liveness")
def liveness(settings: Settings = Depends(get_settings_dependency)) -> SuccessEnvelope[LivenessData]:
    data = LivenessData(service=settings.APP_NAME, version=settings.APP_VERSION, environment=settings.ENVIRONMENT)
    return envelope(data, "API is running")


@router.get(
    "/ready",
    response_model=SuccessEnvelope[ReadinessData],
    responses={503: {"model": ErrorEnvelope, "description": "A required dependency is not ready"}},
    summary="Readiness",
)
def readiness(request: Request, engine: Engine = Depends(get_engine)) -> SuccessEnvelope[ReadinessData]:
    probe = probe_database(engine)
    if probe.reachable:
        request.app.state.last_database_success = probe.checked_at

    reason = None
    if not probe.reachable:
        reason = "Database is unreachable"
    elif not probe.migrations_current:
        reason = "Database schema is not at the migration head"

    database = DatabaseCheck(
        status="PASS" if reason is None else "FAIL",
        reachable=probe.reachable,
        migrations_current=probe.migrations_current,
        latency_ms=probe.latency_ms,
        reason=reason,
    )
    storage_health = request.app.state.storage.health()
    storage = StorageCheck(
        status="PASS" if storage_health.writable else "FAIL",
        writable=storage_health.writable,
        reason=None if storage_health.writable else "Evidence storage is not writable",
    )
    checks = ReadinessChecks(database=database, storage=storage)
    if database.status == "FAIL" or storage.status == "FAIL":
        raise NextronError(
            503, ErrorCode.SERVICE_NOT_READY, "The API is not ready to serve requests", {"checks": checks.model_dump()}
        )
    return envelope(ReadinessData(checks=checks), "API is ready")
