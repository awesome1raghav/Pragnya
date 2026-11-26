"""Append-only investigation events: write one, or read a cursor page."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from Database.PostgreSQL.Models import InvestigationEvent


def append(
    session: Session,
    *,
    case_id: uuid.UUID,
    event_type: str,
    actor: str,
    payload: dict[str, Any] | None = None,
    evidence_id: uuid.UUID | None = None,
) -> InvestigationEvent:
    event = InvestigationEvent(
        case_id=case_id, evidence_id=evidence_id, event_type=event_type, actor=actor, payload=payload or {}
    )
    session.add(event)
    return event


def page(
    session: Session,
    *,
    case_id: uuid.UUID | None = None,
    evidence_id: uuid.UUID | None = None,
    after_sequence: int = 0,
    limit: int = 100,
) -> tuple[list[InvestigationEvent], bool]:
    """Events in sequence order after a cursor; returns (events, has_more)."""
    query = select(InvestigationEvent).where(InvestigationEvent.sequence > after_sequence)
    if case_id is not None:
        query = query.where(InvestigationEvent.case_id == case_id)
    if evidence_id is not None:
        query = query.where(InvestigationEvent.evidence_id == evidence_id)
    rows = list(session.scalars(query.order_by(InvestigationEvent.sequence).limit(limit + 1)))
    return rows[:limit], len(rows) > limit


def latest(session: Session, *, case_id: uuid.UUID, limit: int) -> list[InvestigationEvent]:
    query = (
        select(InvestigationEvent)
        .where(InvestigationEvent.case_id == case_id)
        .order_by(InvestigationEvent.sequence.desc())
        .limit(limit)
    )
    return list(session.scalars(query))


def latest_of_types(session: Session, *, evidence_id: uuid.UUID, event_types: tuple[str, ...]) -> InvestigationEvent | None:
    query = (
        select(InvestigationEvent)
        .where(InvestigationEvent.evidence_id == evidence_id, InvestigationEvent.event_type.in_(event_types))
        .order_by(InvestigationEvent.sequence.desc())
        .limit(1)
    )
    return session.scalars(query).first()


def count_for_case(session: Session, case_id: uuid.UUID) -> int:
    return session.scalar(select(func.count()).where(InvestigationEvent.case_id == case_id)) or 0
