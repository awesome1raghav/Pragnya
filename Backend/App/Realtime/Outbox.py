"""Publishing to the transactional outbox (plan decision D-10).

`publish` only adds a row to the caller's session; it never commits. The caller commits it together with
the domain change it describes, so an event exists exactly when that change exists. The dispatcher
(Realtime/Dispatcher.py) delivers committed events to WebSocket clients and the notification consumer.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from Database.PostgreSQL.Models import OutboxEvent


def publish(
    session: Session,
    event_type: str,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    case_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    module_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        case_id=case_id,
        job_id=job_id,
        module_id=module_id,
        payload=payload or {},
    )
    session.add(event)
    return event


def latest_sequence(session: Session) -> int:
    return session.scalar(select(func.coalesce(func.max(OutboxEvent.sequence), 0))) or 0


def events_after(
    session: Session,
    after: int,
    *,
    limit: int = 500,
    case_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> list[OutboxEvent]:
    query = select(OutboxEvent).where(OutboxEvent.sequence > after)
    if case_id is not None:
        query = query.where(OutboxEvent.case_id == case_id)
    if job_id is not None:
        query = query.where(OutboxEvent.job_id == job_id)
    return list(session.scalars(query.order_by(OutboxEvent.sequence).limit(limit)))


def as_message(event: OutboxEvent) -> dict[str, Any]:
    """The wire form sent to WebSocket clients (and returned by GET /events/outbox)."""
    return {
        "sequence": event.sequence,
        "event_id": str(event.id),
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id),
        "case_id": str(event.case_id) if event.case_id else None,
        "job_id": str(event.job_id) if event.job_id else None,
        "module_id": event.module_id,
        "payload": event.payload,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
