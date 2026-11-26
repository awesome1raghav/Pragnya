"""Global search (plan decision D-20): one endpoint the frontend's search box calls.

Searches investigations, evidence, sources (URL, title), current findings (title, type), reports (number) and
reviews (rationale). The response lists what it searched, so the UI never implies it searched anything else.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from Backend.App.Dependencies import get_db_session
from Backend.App.Schemas.Common import SuccessEnvelope, envelope
from Database.PostgreSQL.Models import AnalysisFinding, AnalysisResult, Case, Report, Review, SourceRecord
from Database.PostgreSQL.Repositories import CaseRepository, EvidenceRepository

router = APIRouter(tags=["Search"])

SEARCHED = ["CASE", "EVIDENCE", "SOURCE", "FINDING", "REPORT", "REVIEW"]
NOT_SEARCHABLE_YET: list[str] = []


class SearchHit(BaseModel):
    type: Literal["CASE", "EVIDENCE", "SOURCE", "FINDING", "REPORT", "REVIEW"]
    id: uuid.UUID
    title: str
    subtitle: str
    case_id: uuid.UUID
    case_number: str
    evidence_id: uuid.UUID | None = None  # the evidence a finding is about, when there is one


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
    searched_types: list[str]
    not_searchable_yet: list[str]


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"  # ILIKE escapes with backslash


@router.get("/search", response_model=SuccessEnvelope[SearchResults], summary="Search investigations, evidence, sources, findings, reports and reviews")
def search(
    q: str = Query(min_length=2, max_length=200, description="Case title/number, evidence filename/number or SHA-256 prefix, source URL/title, "
                                                            "finding title/type, report number (RPT-0001), review rationale"),
    limit: int = Query(default=8, ge=1, le=25, description="Maximum hits per resource type"),
    session: Session = Depends(get_db_session),
):
    text = q.strip()
    hits: list[SearchHit] = []
    for case in CaseRepository.search(session, text, limit=limit):
        hits.append(SearchHit(
            type="CASE", id=case.id, title=case.title, subtitle=f"{case.display_number} · {case.status}",
            case_id=case.id, case_number=case.display_number,
        ))
    for evidence, case_number, case_title in EvidenceRepository.search(session, text, limit=limit):
        number = f"CASE-{case_number:04d}"
        hits.append(SearchHit(
            type="EVIDENCE", id=evidence.id, title=evidence.original_filename,
            subtitle=f"{evidence.display_number} · {evidence.media_type} · {number} {case_title}",
            case_id=evidence.case_id, case_number=number,
        ))
    like = _like(text)
    numbered = lambda prefix: int(text.upper().removeprefix(prefix)) if text.upper().removeprefix(prefix).isdigit() else -1  # noqa: E731
    case_of = lambda cid: session.get(Case, cid)  # noqa: E731
    for src in session.scalars(select(SourceRecord).where(or_(SourceRecord.normalized_url.ilike(like), SourceRecord.title.ilike(like),
                                                               SourceRecord.source_number == numbered("SRC-")))
                               .order_by(SourceRecord.created_at.desc()).limit(limit)):
        c = case_of(src.case_id)
        hits.append(SearchHit(type="SOURCE", id=src.id, title=src.title or src.normalized_url, case_id=c.id, case_number=c.display_number,
                              subtitle=f"{src.display_number} · {src.state.replace('_', ' ').lower()} · {src.normalized_url}"))
    findings = session.scalars(select(AnalysisFinding).join(AnalysisResult, AnalysisResult.id == AnalysisFinding.result_id)
                               .where(AnalysisResult.superseded_at.is_(None),
                                      or_(AnalysisFinding.title.ilike(like), AnalysisFinding.finding_type.ilike(like.replace(" ", r"\_"))))
                               .order_by(AnalysisFinding.created_at.desc()).limit(limit * 3)).all()
    seen: set = set()
    for f in findings:
        key = (f.module_id, f.finding_type, f.title, tuple(f.evidence_ids))
        if key in seen or len(seen) >= limit:
            continue
        seen.add(key)
        c = case_of(f.case_id)
        hits.append(SearchHit(type="FINDING", id=f.id, title=f.title, case_id=c.id, case_number=c.display_number,
                              evidence_id=f.evidence_ids[0] if f.evidence_ids else None,
                              subtitle=f"{f.module_id} · {f.assertion.lower()} · {c.display_number}"))
    for r in session.scalars(select(Report).where(Report.report_number == numbered("RPT-")).limit(limit)):
        c = case_of(r.case_id)
        hits.append(SearchHit(type="REPORT", id=r.id, title=f"{r.display_number} version {r.version}", case_id=c.id, case_number=c.display_number,
                              subtitle=f"{r.kind.title()} · {r.state.lower()} · {c.display_number} {c.title}"))
    for v in session.scalars(select(Review).where(or_(Review.rationale.ilike(like), Review.review_number == numbered("REV-")))
                             .order_by(Review.created_at.desc()).limit(limit)):
        c = case_of(v.case_id)
        hits.append(SearchHit(type="REVIEW", id=v.id, title=v.rationale[:120], case_id=c.id, case_number=c.display_number,
                              subtitle=f"{v.display_number} · {v.subject_type.replace('_', ' ').lower()} · {v.decision.replace('_', ' ').lower()} · {c.display_number}"))
    results = SearchResults(query=text, hits=hits, searched_types=SEARCHED, not_searchable_yet=NOT_SEARCHABLE_YET)
    return envelope(results, f"{len(hits)} result{'s' if len(hits) != 1 else ''}")
