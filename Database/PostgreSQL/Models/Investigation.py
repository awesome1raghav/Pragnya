"""Step 7 records: evidence-graph snapshots (NEX-EGC), reviews (NEX-INV) and report versions (NEX-RPT).

graph_snapshots  one per NEX-EGC execution: the whole case graph as built from PostgreSQL records (append-only).
                 Neo4j is a projection of the latest snapshot and can be rebuilt from here at any time.
reviews          an investigator's decision about one subject (a finding, a lineage relationship, or the case
                 conclusion), with a rationale. Append-only: a new decision on the same subject is a new version,
                 and the latest version is current. Reviews never alter the findings they are about.
reports          one row per generated report version; its JSON and PDF are write-once files with their SHA-256.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

REVIEW_SUBJECTS = ("FINDING", "RELATIONSHIP", "CASE_CONCLUSION")
REVIEW_DECISIONS = ("ACCEPTED", "REJECTED", "INCONCLUSIVE", "NEEDS_MORE_EVIDENCE")
REPORT_KINDS = ("DRAFT", "FINAL")
REPORT_STATES = ("QUEUED", "GENERATED", "FAILED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"
    __table_args__ = (Index("ix_graph_snapshots_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_executions.id", ondelete="RESTRICT"))
    nodes: Mapped[list] = mapped_column(JSONB)
    edges: Mapped[list] = mapped_column(JSONB)
    counts: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(_in("subject_type", REVIEW_SUBJECTS), name="subject_type_valid"),
        CheckConstraint(_in("decision", REVIEW_DECISIONS), name="decision_valid"),
        CheckConstraint("length(rationale) >= 3", name="rationale_required"),
        UniqueConstraint("subject_type", "subject_id", "version", name="uq_reviews_subject_version"),
        Index("ix_reviews_case_id_created_at", "case_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))   # finding, relationship, or the case itself
    version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    reconstruction_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="RESTRICT"))
    reviewer: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def display_number(self) -> str:
        return f"REV-{self.review_number:04d}"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(_in("kind", REPORT_KINDS), name="kind_valid"),
        CheckConstraint(_in("state", REPORT_STATES), name="state_valid"),
        UniqueConstraint("case_id", "version", name="uq_reports_case_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column(String(16), default="QUEUED")
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    json_sha256: Mapped[str | None] = mapped_column(String(64))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    json_key: Mapped[str | None] = mapped_column(String(255))
    pdf_key: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # counts frozen into the report
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def display_number(self) -> str:
        return f"RPT-{self.report_number:04d}"
