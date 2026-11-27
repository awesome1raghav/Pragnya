"""Workspace summaries for the dashboard and the investigation workspace (UX transformation).

Everything here is derived from stored records at request time; nothing is estimated or cached:
  /investigation-progress   per investigation: where it stands (evidence → analysis → review → report), the next
                            action, and a real evidence image to show (the newest preserved image, if any).
  /attention                what needs the operator now: failed runs, unread alerts (integrity, reports, sources),
                            and finished analyses with inferences that have no case conclusion yet.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from Backend.App.Dependencies import get_db_session
from Backend.App.Schemas.Common import SuccessEnvelope, envelope
from Database.PostgreSQL.Models import AnalysisFinding, AnalysisJob, AnalysisResult, Case, Evidence, Notification, Report, Review
from Database.PostgreSQL.Repositories.CaseRepository import SORTABLE, is_test_record

router = APIRouter(tags=["Workspace summaries"])
Stage = Literal["ACQUIRE", "ANALYSE", "REVIEW", "REPORT", "DONE"]


class Progress(BaseModel):
    case_id: uuid.UUID
    case_number: str
    title: str
    status: str
    test_record: bool
    evidence: int
    by_media: dict[str, int]
    image_evidence_id: uuid.UUID | None  # newest preserved image: an actual item, for a preview
    runs_active: int
    last_run_state: str | None
    inferences: int
    conclusion: str | None  # decision of the current case-conclusion review
    reports: int
    final_report: bool
    stage: Stage
    next_action: str


def _progress(session: Session, case: Case) -> Progress:
    by_media = dict(session.execute(select(Evidence.media_type, func.count()).where(Evidence.case_id == case.id).group_by(Evidence.media_type)).all())
    image = session.scalar(select(Evidence.id).where(Evidence.case_id == case.id, Evidence.media_type == "IMAGE").order_by(Evidence.evidence_number.desc()).limit(1))
    runs = session.execute(select(AnalysisJob.state).where(AnalysisJob.case_id == case.id, AnalysisJob.job_type == "INVESTIGATION_RUN")
                           .order_by(AnalysisJob.created_at.desc())).scalars().all()
    active = sum(s in ("QUEUED", "RUNNING") for s in runs)
    inferences = session.scalar(select(func.count()).select_from(AnalysisFinding).join(AnalysisResult, AnalysisResult.id == AnalysisFinding.result_id)
                                .where(AnalysisFinding.case_id == case.id, AnalysisFinding.assertion == "INFERENCE", AnalysisResult.superseded_at.is_(None))) or 0
    conclusion = session.scalar(select(Review.decision).where(Review.case_id == case.id, Review.subject_type == "CASE_CONCLUSION")
                                .order_by(Review.version.desc()).limit(1))
    reports = session.execute(select(Report.kind).where(Report.case_id == case.id, Report.state == "GENERATED")).scalars().all()
    evidence = sum(by_media.values())
    if not evidence:
        stage, action = "ACQUIRE", "Add the evidence to examine"
    elif active or not runs:
        stage, action = "ANALYSE", "Analysis is running" if active else "Run the analysis"
    elif conclusion is None:
        stage, action = "REVIEW", f"Review {inferences} inference{'s' if inferences != 1 else ''} and record a conclusion" if inferences else "Record a case conclusion"
    elif "FINAL" not in reports:
        stage, action = "REPORT", "Generate the final report"
    else:
        stage, action = "DONE", "Final report generated"
    return Progress(case_id=case.id, case_number=case.display_number, title=case.title, status=case.status, test_record=is_test_record(case.title),
                    evidence=evidence, by_media=by_media, image_evidence_id=image, runs_active=active, last_run_state=runs[0] if runs else None,
                    inferences=inferences, conclusion=conclusion, reports=len(reports), final_report="FINAL" in reports, stage=stage, next_action=action)


@router.get("/investigation-progress", response_model=SuccessEnvelope[list[Progress]], summary="Where each investigation stands, from its records")
def investigation_progress(case_ids: list[uuid.UUID] = Query(max_length=50), session: Session = Depends(get_db_session)):
    cases = {c.id: c for c in session.scalars(select(Case).where(Case.id.in_(case_ids)))}
    return envelope([_progress(session, cases[i]) for i in case_ids if i in cases], "Progress retrieved successfully")


class AttentionItem(BaseModel):
    kind: Literal["RUN_FAILED", "ALERT", "WARNING", "AWAITING_REVIEW"]
    title: str
    detail: str | None
    link: str | None
    case_id: uuid.UUID | None
    at: str


@router.get("/attention", response_model=SuccessEnvelope[list[AttentionItem]], summary="What needs the operator, most recent first")
def attention(hide_test_records: bool = False, limit: int = Query(default=8, ge=1, le=50), session: Session = Depends(get_db_session)):
    items: list[AttentionItem] = []
    titles = dict(session.execute(select(Case.id, Case.title)).all())
    keep = lambda case_id: not (hide_test_records and case_id and is_test_record(titles.get(case_id, "")))  # noqa: E731
    for n in session.scalars(select(Notification).where(Notification.read_at.is_(None), Notification.severity.in_(("ALERT", "WARNING")))
                             .order_by(Notification.sequence.desc()).limit(200)):
        if n.event_type == "job.partially_completed" or not keep(n.case_id):
            continue  # partial runs are normal when a detector is absent; they are not a call to act
        items.append(AttentionItem(kind="RUN_FAILED" if n.event_type == "job.failed" else n.severity, title=n.title, detail=n.body,
                                   link=n.link, case_id=n.case_id, at=n.created_at.isoformat()))
    last = SORTABLE["last_activity_at"]
    recent = session.execute(select(Case, last.label("last")).where(Case.status != "ARCHIVED").order_by(last.desc()).limit(40)).all()
    for c, last_at in recent:
        if not keep(c.id):
            continue
        p = _progress(session, c)
        if p.stage == "REVIEW" and p.inferences:
            items.append(AttentionItem(kind="AWAITING_REVIEW", title=f"{p.case_number}: {p.next_action}", detail=c.title,
                                       link=f"/investigations/{c.id}/review", case_id=c.id, at=last_at.isoformat()))
    items.sort(key=lambda i: i.at, reverse=True)
    return envelope(items[:limit], f"{len(items)} items need attention")
