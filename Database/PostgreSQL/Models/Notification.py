"""Notifications derived from committed outbox events (plan decision D-21).

One notification per source event at most (unique `event_id`), so a consumer that re-reads the outbox
after a restart never duplicates them. Only `read_at` changes after creation.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

NOTIFICATION_SEVERITIES = ("INFO", "WARNING", "ALERT")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'ALERT')", name="severity_valid"),
        Index("ix_notifications_unread", "sequence", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("outbox_events.id", ondelete="RESTRICT"), unique=True)
    event_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))  # an application path, e.g. /evidence/<id>/analysis
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
