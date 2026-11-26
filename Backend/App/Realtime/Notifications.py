"""Notifications derived from outbox events (plan decision D-21), and the reads and updates the API needs.

The consumer reads the outbox after its checkpoint, turns the events worth telling the operator about into
notifications, and moves the checkpoint, all in one transaction. A notification's unique `event_id` makes
re-reading harmless, so the consumer can run in every API process and survive restarts without duplicates.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Realtime import Outbox
from Backend.App.Realtime.Cursor import GapSafeCursor
from Database.PostgreSQL.Models import Notification, OutboxCheckpoint, OutboxEvent

CONSUMER = "notifications"


def _counts(payload: dict) -> str:
    progress = payload.get("progress") or {}
    by_state = progress.get("by_state") or {}
    if not by_state:
        return ""
    parts = [f"{n} {state.lower().replace('_', ' ')}" for state, n in sorted(by_state.items())]
    return f" Modules: {', '.join(parts)}."


def _link(event: OutboxEvent) -> str | None:
    evidence_id = (event.payload or {}).get("evidence_id")
    if evidence_id:
        return f"/evidence/{evidence_id}/analysis"
    return f"/investigations/{event.case_id}/analysis" if event.case_id else None


def describe(event: OutboxEvent) -> tuple[str, str, str | None, str | None] | None:
    """(severity, title, body, link) for events that become notifications; None for the rest."""
    p = event.payload or {}
    job = p.get("job_number", "A job")
    t = event.event_type
    if t == "job.completed":
        return "INFO", f"{job} completed", "Every planned module completed or did not apply." + _counts(p), _link(event)
    if t == "job.partially_completed":
        return "WARNING", f"{job} completed partially", "Some modules failed or are not available in this build." + _counts(p), _link(event)
    if t == "job.failed":
        message = (p.get("error") or {}).get("message") or "No module produced output."
        return "ALERT", f"{job} failed", message + _counts(p), _link(event)
    if t == "job.cancelled":
        return "INFO", f"{job} cancelled", "Modules that had not started were not run.", _link(event)
    if t in ("evidence.integrity_mismatch", "evidence.integrity_missing"):
        what = "do not match the recorded SHA-256" if t.endswith("mismatch") else "are missing from storage"
        return ("ALERT", f"{p.get('evidence_number', 'Evidence')}: integrity check failed",
                f"The stored bytes {what}.", f"/evidence/{event.aggregate_id}/integrity")
    return None


class NotificationConsumer:
    def __init__(self, *, gap_timeout: float = 15.0):
        self.cursor: GapSafeCursor | None = None
        self.gap_timeout = gap_timeout

    def process(self, session: Session, *, batch: int = 500) -> int:
        """Handles one batch; returns how many notifications were created. Commits."""
        checkpoint = session.get(OutboxCheckpoint, CONSUMER, with_for_update=True)
        if checkpoint is None:
            session.execute(insert(OutboxCheckpoint).values(consumer=CONSUMER, last_sequence=0).on_conflict_do_nothing())
            checkpoint = session.get(OutboxCheckpoint, CONSUMER, with_for_update=True)
        if self.cursor is None or self.cursor.position < checkpoint.last_sequence:
            self.cursor = GapSafeCursor(checkpoint.last_sequence, gap_timeout=self.gap_timeout)
        created = 0
        for event in Outbox.events_after(session, self.cursor.position, limit=batch):
            if not self.cursor.is_new(event.sequence):
                continue
            described = describe(event)
            if described:
                severity, title, body, link = described
                created += session.execute(
                    insert(Notification).values(id=uuid.uuid4(), event_id=event.id, event_type=event.event_type, severity=severity,
                                                title=title[:200], body=body, link=link, case_id=event.case_id, job_id=event.job_id)
                    .on_conflict_do_nothing(index_elements=["event_id"])
                ).rowcount
            self.cursor.mark(event.sequence)
        self.cursor.tick()
        if self.cursor.position > checkpoint.last_sequence:
            checkpoint.last_sequence = self.cursor.position
            checkpoint.updated_at = datetime.now(timezone.utc)
        session.commit()
        return created


# ── API reads and updates ────────────────────────────────────────────────────────────────────

class NotificationRead(BaseModel):
    notification_id: uuid.UUID
    sequence: int
    event_type: str
    severity: str
    title: str
    body: str | None
    link: str | None
    case_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_at: datetime
    read_at: datetime | None

    @classmethod
    def of(cls, n: Notification) -> "NotificationRead":
        return cls(notification_id=n.id, sequence=n.sequence, event_type=n.event_type, severity=n.severity, title=n.title,
                   body=n.body, link=n.link, case_id=n.case_id, job_id=n.job_id, created_at=n.created_at, read_at=n.read_at)


class NotificationSummary(BaseModel):
    unread: int
    total: int


def list_page(session: Session, *, page: int, page_size: int, unread_only: bool) -> tuple[list[NotificationRead], int]:
    conditions: list[Any] = [Notification.read_at.is_(None)] if unread_only else []
    total = session.scalar(select(func.count()).select_from(Notification).where(*conditions)) or 0
    rows = session.scalars(select(Notification).where(*conditions).order_by(Notification.sequence.desc())
                           .offset((page - 1) * page_size).limit(page_size))
    return [NotificationRead.of(n) for n in rows], total


def summary(session: Session) -> NotificationSummary:
    total = session.scalar(select(func.count()).select_from(Notification)) or 0
    unread = session.scalar(select(func.count()).select_from(Notification).where(Notification.read_at.is_(None))) or 0
    return NotificationSummary(unread=unread, total=total)


def mark_read(session: Session, notification_id: uuid.UUID) -> NotificationRead:
    n = session.get(Notification, notification_id)
    if n is None:
        raise NextronError(404, ErrorCode.NOTIFICATION_NOT_FOUND, "The requested notification does not exist")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        session.commit()
    return NotificationRead.of(n)


def mark_all_read(session: Session) -> int:
    count = session.execute(update(Notification).where(Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc))).rowcount
    session.commit()
    return count
