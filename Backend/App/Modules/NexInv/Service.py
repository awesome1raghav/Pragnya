"""NEX-INV Review & Decision (archive §4, module 17): an investigator's decisions, kept apart from what the modules found.

A review is about one subject in the case: a FINDING, a lineage RELATIONSHIP, or the CASE_CONCLUSION. It records a
decision (ACCEPTED, REJECTED, INCONCLUSIVE, NEEDS_MORE_EVIDENCE) and a rationale. Reviews are append-only: deciding
again on the same subject adds version n+1, and the latest version is current. A finding or relationship is never
altered by a review. A case conclusion needs a current, completed NEX-REC reconstruction (edge NEX-REC -> NEX-INV),
and records which reconstruction it reviewed.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Realtime import Outbox
from Database.PostgreSQL.Models import AnalysisFinding, AnalysisResult, MediaRelationship, Review


def current_reconstruction(session: Session, case_id: uuid.UUID) -> AnalysisResult | None:
    return session.scalars(select(AnalysisResult).where(AnalysisResult.case_id == case_id, AnalysisResult.module_id == "NEX-REC",
                                                        AnalysisResult.superseded_at.is_(None), AnalysisResult.status == "COMPLETED")
                           .order_by(AnalysisResult.created_at.desc()).limit(1)).first()


def _check_subject(session: Session, case_id: uuid.UUID, subject_type: str, subject_id: uuid.UUID) -> uuid.UUID | None:
    if subject_type == "CASE_CONCLUSION":
        if subject_id != case_id:
            raise NextronError(422, ErrorCode.VALIDATION_ERROR, "A case conclusion's subject is the case itself")
        rec = current_reconstruction(session, case_id)
        if rec is None:
            raise NextronError(409, ErrorCode.RECONSTRUCTION_REQUIRED, "A case conclusion needs a completed reconstruction (NEX-REC) first")
        return rec.id
    model = AnalysisFinding if subject_type == "FINDING" else MediaRelationship
    row = session.get(model, subject_id)
    if row is None or row.case_id != case_id:
        raise NextronError(404, ErrorCode.REVIEW_SUBJECT_NOT_FOUND, f"No {subject_type.lower()} with this id in this case")
    return None


def record(session: Session, case_id: uuid.UUID, *, subject_type: str, subject_id: uuid.UUID, decision: str, rationale: str, actor: str) -> Review:
    Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))  # the case lock serialises versions
    reconstruction = _check_subject(session, case_id, subject_type, subject_id)
    version = (session.scalar(select(func.max(Review.version)).where(Review.subject_type == subject_type, Review.subject_id == subject_id)) or 0) + 1
    review = Review(case_id=case_id, subject_type=subject_type, subject_id=subject_id, version=version, decision=decision,
                    rationale=rationale.strip(), reconstruction_result_id=reconstruction, reviewer=actor)
    session.add(review)
    session.flush()
    Outbox.publish(session, "review.recorded", aggregate_type="review", aggregate_id=review.id, case_id=case_id,
                   payload={"review_number": review.display_number, "subject_type": subject_type, "subject_id": str(subject_id),
                            "version": version, "decision": decision})
    session.commit()
    return review


def list_reviews(session: Session, case_id: uuid.UUID, *, current_only: bool = False) -> list[Review]:
    rows = session.scalars(select(Review).where(Review.case_id == case_id).order_by(Review.review_number.desc())).all()
    if not current_only:
        return list(rows)
    seen, current = set(), []
    for r in rows:
        if (r.subject_type, r.subject_id) not in seen:
            seen.add((r.subject_type, r.subject_id))
            current.append(r)
    return current


def current_conclusion(session: Session, case_id: uuid.UUID) -> Review | None:
    return session.scalars(select(Review).where(Review.case_id == case_id, Review.subject_type == "CASE_CONCLUSION")
                           .order_by(Review.version.desc()).limit(1)).first()
