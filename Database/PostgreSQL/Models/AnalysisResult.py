"""A module's result envelope for one execution (the Flowchart B §5.2 contract, stored whole as JSONB).

Results are immutable: a database trigger rejects every change except marking the result superseded
(when new evidence or sources make it stale, plan decision D-14). Superseded results stay readable, so
reports and reviews keep pointing at the versions they used.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base
from Database.PostgreSQL.Models.AnalysisExecution import EXECUTION_TERMINAL_STATES, MODULE_ID_PATTERN

RESULT_STATUSES = tuple(s for s in EXECUTION_TERMINAL_STATES)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in RESULT_STATUSES)})", name="status_valid"),
        CheckConstraint(f"module_id ~ '{MODULE_ID_PATTERN}'", name="module_id_format"),
        CheckConstraint("(superseded_at IS NULL) = (superseded_by IS NULL)", name="supersession_complete"),
        Index("ix_analysis_results_case_id_module_id", "case_id", "module_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_executions.id", ondelete="RESTRICT"), unique=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    module_id: Mapped[str] = mapped_column(String(8))
    schema_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    envelope: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="RESTRICT"))
