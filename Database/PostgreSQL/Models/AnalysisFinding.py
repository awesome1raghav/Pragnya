"""Individual findings from a result, as rows so they can be queried, reviewed and cited (append-only).

`assertion` separates what was measured (OBSERVATION) from what is concluded from it (INFERENCE) and from
what could not be decided (INCONCLUSIVE). `score` is the method's raw number with its `score_kind`;
`confidence` exists only with a stated basis and a calibrated score (no invented confidence).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base
from Database.PostgreSQL.Models.AnalysisExecution import MODULE_ID_PATTERN

ASSERTIONS = ("OBSERVATION", "INFERENCE", "INCONCLUSIVE")
SCORE_KINDS = ("METHOD_SPECIFIC", "DISTANCE", "SIMILARITY", "CALIBRATED_PROBABILITY")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"
    __table_args__ = (
        CheckConstraint(_in("assertion", ASSERTIONS), name="assertion_valid"),
        CheckConstraint(f"score_kind IS NULL OR {_in('score_kind', SCORE_KINDS)}", name="score_kind_valid"),
        CheckConstraint("(score IS NULL) = (score_kind IS NULL)", name="score_has_kind"),
        CheckConstraint(
            "confidence IS NULL OR (score_kind = 'CALIBRATED_PROBABILITY' AND confidence_basis IS NOT NULL AND confidence BETWEEN 0 AND 1)",
            name="confidence_only_when_calibrated",
        ),
        CheckConstraint(f"module_id ~ '{MODULE_ID_PATTERN}'", name="module_id_format"),
        Index("ix_analysis_findings_case_id_module_id", "case_id", "module_id"),
        Index("ix_analysis_findings_evidence_ids", "evidence_ids", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    module_id: Mapped[str] = mapped_column(String(8))
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    assertion: Mapped[str] = mapped_column(String(16))
    finding_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    score_kind: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_basis: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)  # the full finding as in the result envelope
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
