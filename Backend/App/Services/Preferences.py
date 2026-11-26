"""Operator preferences (Step 8): what the operator chooses, stored in PostgreSQL, applied by the backend.

  notifications   which kinds of events become notifications. Integrity failures always do and cannot be turned off.
  analysis        whether a preserved upload or retrieved source queues its investigation run automatically
                  (unset: the server's AUTO_ANALYZE_ON_UPLOAD).
  reports         the format the Reports page downloads by default.

Updates carry the version they were based on; a stale version is refused with 409 PREFERENCES_CONFLICT and the
current document, so two tabs never silently overwrite each other. Every update publishes `preferences.updated`, so
other open tabs refresh.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Realtime import Outbox
from Database.PostgreSQL.Models import OperatorPreferences

NAMESPACE = uuid.UUID("6f1c3f5e-6d1b-4f0a-9a54-6e6578747270")  # fixed aggregate id for preference events


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runs_completed: bool = True
    runs_partial: bool = True
    runs_failed: bool = True
    runs_cancelled: bool = True
    sources: bool = Field(default=True, description="A source that could not be retrieved")
    reports: bool = Field(default=True, description="A report generated or failed")


class AnalysisPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_analyze_on_upload: bool | None = Field(default=None, description="null: follow the server's AUTO_ANALYZE_ON_UPLOAD")


class ReportPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_download: Literal["pdf", "json"] = "pdf"


class PreferenceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notifications: NotificationPreferences = NotificationPreferences()
    analysis: AnalysisPreferences = AnalysisPreferences()
    reports: ReportPreferences = ReportPreferences()


class PreferencesRead(BaseModel):
    operator: str
    version: int = Field(description="Send it back with an update; 0 means nothing has been saved yet (defaults)")
    preferences: PreferenceDocument
    effective: dict = Field(description="What the backend applies now, after server defaults")
    updated_at: datetime | None


def _row(session: Session, operator: str, *, lock: bool = False) -> OperatorPreferences | None:
    return session.get(OperatorPreferences, operator, with_for_update=lock)


def document(session: Session, operator: str) -> PreferenceDocument:
    row = _row(session, operator)
    return PreferenceDocument.model_validate(row.preferences) if row else PreferenceDocument()


def auto_analyze(session: Session, settings: Settings) -> bool:
    chosen = document(session, settings.OPERATOR_NAME).analysis.auto_analyze_on_upload
    return settings.AUTO_ANALYZE_ON_UPLOAD if chosen is None else chosen


def read(session: Session, settings: Settings) -> PreferencesRead:
    row = _row(session, settings.OPERATOR_NAME)
    doc = PreferenceDocument.model_validate(row.preferences) if row else PreferenceDocument()
    effective = {"auto_analyze_on_upload": settings.AUTO_ANALYZE_ON_UPLOAD if doc.analysis.auto_analyze_on_upload is None
                 else doc.analysis.auto_analyze_on_upload, "integrity_notifications": "always"}
    return PreferencesRead(operator=settings.OPERATOR_NAME, version=row.version if row else 0, preferences=doc, effective=effective,
                           updated_at=row.updated_at if row else None)


def _merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        out[k] = _merge(out.get(k) or {}, v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def update(session: Session, settings: Settings, *, expected_version: int, patch: dict) -> PreferencesRead:
    operator = settings.OPERATOR_NAME
    row = _row(session, operator, lock=True)
    current = row.version if row else 0
    if expected_version != current:
        session.rollback()
        raise NextronError(409, ErrorCode.PREFERENCES_CONFLICT, "Preferences were changed elsewhere (another tab?); reload and apply again",
                           {"current_version": current, "current": read(session, settings).model_dump(mode="json")})
    base = (row.preferences if row else {}) or {}
    try:
        doc = PreferenceDocument.model_validate(_merge(PreferenceDocument.model_validate(base).model_dump(), patch))
    except ValueError as exc:
        session.rollback()
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown or invalid preference", {"error": str(exc)[:500]}) from exc
    if row is None:
        row = OperatorPreferences(operator=operator, preferences=doc.model_dump(), version=1)
        session.add(row)
    else:
        row.preferences, row.version = doc.model_dump(), row.version + 1
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    Outbox.publish(session, "preferences.updated", aggregate_type="preferences", aggregate_id=NAMESPACE,
                   payload={"operator": operator, "version": row.version})
    session.commit()
    return read(session, settings)
