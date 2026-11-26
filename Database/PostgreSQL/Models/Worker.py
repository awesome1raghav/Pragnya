"""Registered worker processes and their heartbeats (GET /system/workers reads these)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

WORKER_STATES = ("RUNNING", "STOPPED")


class WorkerProcess(Base):
    __tablename__ = "workers"
    __table_args__ = (CheckConstraint("state IN ('RUNNING', 'STOPPED')", name="state_valid"),)

    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255))
    pid: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(50))
    state: Mapped[str] = mapped_column(String(16), default="RUNNING")
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
