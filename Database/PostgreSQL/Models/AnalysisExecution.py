"""One module's execution for one scope (an evidence item, a pair, or the whole case) within a job.

Each retry is a new row (attempt + 1), so the history of every attempt is kept. The input fingerprint
is a SHA-256 over the module version, its parameters, the referenced input result IDs and the evidence
digests: a COMPLETED execution with the same module, scope and fingerprint makes another run redundant,
and a partial unique index enforces it (plan decision D-8).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

EXECUTION_STATES = (
    "PENDING", "QUEUED", "WAITING_FOR_DEPENDENCIES", "RUNNING",
    "COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED", "SKIPPED", "UNAVAILABLE",
)
EXECUTION_TERMINAL_STATES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED", "SKIPPED", "UNAVAILABLE")
# states that must say why (Flowchart B §5.1: "a skipped or failed module must have an associated explanation")
EXPLAINED_STATES = ("FAILED", "CANCELLED", "SKIPPED", "UNAVAILABLE", "PARTIALLY_COMPLETED")
SCOPE_KINDS = ("EVIDENCE", "PAIR", "CASE")
MODULE_ID_PATTERN = "^NEX-[A-Z]{2,3}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AnalysisExecution(Base):
    __tablename__ = "analysis_executions"
    __table_args__ = (
        CheckConstraint(_in("state", EXECUTION_STATES), name="state_valid"),
        CheckConstraint(_in("scope_kind", SCOPE_KINDS), name="scope_kind_valid"),
        CheckConstraint(f"module_id ~ '{MODULE_ID_PATTERN}'", name="module_id_format"),
        CheckConstraint("input_fingerprint ~ '^[0-9a-f]{64}$'", name="input_fingerprint_hex"),
        CheckConstraint("attempt >= 1", name="attempt_positive"),
        CheckConstraint(f"NOT ({_in('state', EXPLAINED_STATES)}) OR state_reason IS NOT NULL", name="explained_states_have_reason"),
        CheckConstraint(f"({_in('state', EXECUTION_TERMINAL_STATES)}) = (finished_at IS NOT NULL)", name="finished_at_matches_state"),
        UniqueConstraint("job_id", "module_id", "scope_ref", "attempt", name="uq_analysis_executions_job_module_scope_attempt"),
        Index("ix_analysis_executions_job_id", "job_id"),
        Index(
            "uq_analysis_executions_completed_fingerprint", "module_id", "scope_ref", "input_fingerprint",
            unique=True, postgresql_where=text("state = 'COMPLETED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    module_id: Mapped[str] = mapped_column(String(8))
    scope_kind: Mapped[str] = mapped_column(String(16))
    scope_ref: Mapped[str] = mapped_column(String(80))  # evidence UUID, "uuidA:uuidB" for a pair, or the case UUID
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(32), default="PENDING")
    state_reason: Mapped[str | None] = mapped_column(String(64))  # NOT_APPLICABLE, UPSTREAM_FAILED, TIMEOUT …
    state_detail: Mapped[str | None] = mapped_column(Text)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    module_version: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    tool_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    progress: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
