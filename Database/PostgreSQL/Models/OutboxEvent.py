"""Transactional outbox (plan decision D-10).

A service writes its domain change and an outbox event in the same transaction, so an event exists if
and only if the change committed. One dispatcher reads events in `sequence` order and delivers them to
each consumer (WebSocket gateway, notifications, and later the Neo4j and Qdrant projections); each
consumer's progress is its row in `outbox_checkpoints`. Events are append-only.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("event_type ~ '^[a-z]+(\\.[a-z_]+)+$'", name="event_type_format"),
        Index("ix_outbox_events_case_id_sequence", "case_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0", server_default=text("'1.0'"))
    event_type: Mapped[str] = mapped_column(String(64))  # e.g. analysis.module.completed
    aggregate_type: Mapped[str] = mapped_column(String(32))  # case, evidence, job, execution …
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    module_id: Mapped[str | None] = mapped_column(String(8))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxCheckpoint(Base):
    """How far each consumer has processed the outbox."""

    __tablename__ = "outbox_checkpoints"
    __table_args__ = (CheckConstraint("last_sequence >= 0", name="last_sequence_non_negative"),)

    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
