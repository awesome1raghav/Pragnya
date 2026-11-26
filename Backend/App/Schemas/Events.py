"""Investigation event representation and cursor-paged event lists."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from Backend.App.Schemas.Common import Meta
from Database.PostgreSQL.Models import InvestigationEvent


class EventRead(BaseModel):
    event_id: uuid.UUID
    sequence: int = Field(description="Stable increasing cursor; pass as `after` to resume")
    event_type: str
    case_id: uuid.UUID
    evidence_id: uuid.UUID | None
    actor: str
    payload: dict[str, Any]
    occurred_at: datetime

    @classmethod
    def of(cls, event: InvestigationEvent) -> "EventRead":
        return cls(
            event_id=event.id,
            sequence=event.sequence,
            event_type=event.event_type,
            case_id=event.case_id,
            evidence_id=event.evidence_id,
            actor=event.actor,
            payload=event.payload,
            occurred_at=event.occurred_at,
        )


class EventCursor(BaseModel):
    after: int
    next_after: int | None = Field(description="Cursor for the next page; null when there are no more events")
    has_more: bool
    limit: int


class EventPageEnvelope(BaseModel):
    success: Literal[True] = True
    message: str
    data: list[EventRead]
    cursor: EventCursor
    meta: Meta = Field(default_factory=Meta)


def event_page(events: list[InvestigationEvent], has_more: bool, *, after: int, limit: int, message: str) -> EventPageEnvelope:
    items = [EventRead.of(e) for e in events]
    return EventPageEnvelope(
        message=message,
        data=items,
        cursor=EventCursor(after=after, next_after=items[-1].sequence if has_more and items else None, has_more=has_more, limit=limit),
    )
