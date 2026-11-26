"""Durable jobs (plan decision D-7). One table for every kind of background work; only the Job
Service changes a job's state. Workers claim QUEUED jobs with FOR UPDATE SKIP LOCKED, hold a lease
while they work, and renew it with heartbeats; an expired lease makes the job claimable again.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

JOB_TYPES = ("INVESTIGATION_RUN", "SOURCE_RESOLUTION", "REPORT_GENERATION", "PROJECTION_REBUILD")
JOB_STATES = ("QUEUED", "RUNNING", "COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED")
JOB_TERMINAL_STATES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(_in("job_type", JOB_TYPES), name="job_type_valid"),
        CheckConstraint(_in("state", JOB_STATES), name="state_valid"),
        CheckConstraint("attempt >= 0 AND max_attempts >= 1 AND attempt <= max_attempts", name="attempts_valid"),
        CheckConstraint("priority BETWEEN 0 AND 100", name="priority_range"),
        CheckConstraint("timeout_seconds > 0", name="timeout_positive"),
        CheckConstraint("(state = 'RUNNING') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)", name="lease_only_while_running"),
        CheckConstraint(f"({_in('state', JOB_TERMINAL_STATES)}) = (finished_at IS NOT NULL)", name="finished_at_matches_state"),
        # the claim query: highest priority, oldest first, among queued jobs whose retry delay has passed
        Index("ix_analysis_jobs_claim", "priority", "available_at", postgresql_where=text("state = 'QUEUED'")),
        Index("ix_analysis_jobs_case_id_created_at", "case_id", "created_at"),
        Index("ix_analysis_jobs_lease_expires_at", "lease_expires_at", postgresql_where=text("state = 'RUNNING'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    job_type: Mapped[str] = mapped_column(String(32))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    state: Mapped[str] = mapped_column(String(32), default="QUEUED")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    requested_by: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    plan: Mapped[dict | None] = mapped_column(JSONB)  # T-MIR's execution plan snapshot for INVESTIGATION_RUN
    progress: Mapped[dict | None] = mapped_column(JSONB)  # measured progress only (e.g. modules finished / planned)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # retry backoff
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def display_number(self) -> str:
        return f"JOB-{self.job_number:04d}"
