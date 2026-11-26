"""Graph, reconstruction, review and report APIs (NEX-EGC, NEX-REC, NEX-INV, NEX-RPT)."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_actor, get_db_session, get_settings_dependency, get_storage
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexInv import Service as ReviewService
from Backend.App.Modules.NexRpt import Service as ReportService
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Storage.LocalStorage import LocalStorage
from Database.PostgreSQL.Models import AnalysisFinding, GraphSnapshot, Report, Review

router = APIRouter(tags=["Investigation (NEX-EGC, NEX-REC, NEX-INV, NEX-RPT)"])
_CASE_404 = {404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND"}}


class GraphRead(BaseModel):
    snapshot_id: uuid.UUID
    case_id: uuid.UUID
    execution_id: uuid.UUID
    nodes: list[dict]
    edges: list[dict] = Field(description="Each edge names the PostgreSQL record that supports it")
    counts: dict
    created_at: datetime


@router.get("/cases/{case_id}/graph", response_model=SuccessEnvelope[GraphRead],
            responses=_CASE_404 | {409: {"model": ErrorEnvelope, "description": "GRAPH_NOT_BUILT"}}, summary="The latest evidence-graph snapshot")
def case_graph(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    g = session.scalars(select(GraphSnapshot).where(GraphSnapshot.case_id == case_id).order_by(GraphSnapshot.created_at.desc()).limit(1)).first()
    if g is None:
        raise NextronError(409, ErrorCode.GRAPH_NOT_BUILT, "No evidence graph has been built for this case yet; run the case analysis")
    return envelope(GraphRead(snapshot_id=g.id, case_id=g.case_id, execution_id=g.execution_id, nodes=g.nodes, edges=g.edges,
                              counts=g.counts, created_at=g.created_at), "Graph retrieved successfully")


class ReconstructionRead(BaseModel):
    result_id: uuid.UUID | None
    produced_at: datetime | None
    timeline: list[dict] = Field(description="Dated statements in order, each labelled by who states it")
    conflicts: list[dict]


@router.get("/cases/{case_id}/reconstruction", response_model=SuccessEnvelope[ReconstructionRead], responses=_CASE_404,
            summary="The current timeline reconstruction and its time conflicts")
def case_reconstruction(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    rec = ReviewService.current_reconstruction(session, case_id)
    if rec is None:
        return envelope(ReconstructionRead(result_id=None, produced_at=None, timeline=[], conflicts=[]), "No reconstruction yet")
    rows = session.scalars(select(AnalysisFinding).where(AnalysisFinding.result_id == rec.id)).all()
    timeline = next(((f.payload.get("measurement") or {}).get("timeline", []) for f in rows if f.finding_type == "RECONSTRUCTION"), [])
    conflicts = [{"finding_id": str(f.id), "title": f.title, "description": f.description, "evidence_ids": [str(e) for e in f.evidence_ids],
                  "assertion": f.assertion} for f in rows if f.finding_type == "TIME_CONFLICT"]
    return envelope(ReconstructionRead(result_id=rec.id, produced_at=rec.created_at, timeline=timeline, conflicts=conflicts), "Reconstruction retrieved successfully")


class ReviewCreate(BaseModel):
    subject_type: Literal["FINDING", "RELATIONSHIP", "CASE_CONCLUSION"]
    subject_id: uuid.UUID = Field(description="A finding id, a relationship id, or the case id for a case conclusion")
    decision: Literal["ACCEPTED", "REJECTED", "INCONCLUSIVE", "NEEDS_MORE_EVIDENCE"]
    rationale: str = Field(min_length=3, max_length=4000)


class ReviewRead(BaseModel):
    review_id: uuid.UUID
    review_number: str
    case_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    version: int
    decision: str
    rationale: str
    reconstruction_result_id: uuid.UUID | None
    reviewer: str
    created_at: datetime

    @classmethod
    def of(cls, r: Review) -> "ReviewRead":
        return cls(review_id=r.id, review_number=r.display_number, case_id=r.case_id, subject_type=r.subject_type, subject_id=r.subject_id,
                   version=r.version, decision=r.decision, rationale=r.rationale, reconstruction_result_id=r.reconstruction_result_id,
                   reviewer=r.reviewer, created_at=r.created_at)


@router.post("/cases/{case_id}/reviews", status_code=status.HTTP_201_CREATED, response_model=SuccessEnvelope[ReviewRead],
             responses=_CASE_404 | {409: {"model": ErrorEnvelope, "description": "RECONSTRUCTION_REQUIRED or CASE_ARCHIVED"}},
             summary="Record a decision about a finding, a relationship or the case conclusion")
def create_review(case_id: uuid.UUID, body: ReviewCreate, session: Session = Depends(get_db_session), actor: str = Depends(get_actor)):
    r = ReviewService.record(session, case_id, subject_type=body.subject_type, subject_id=body.subject_id, decision=body.decision,
                             rationale=body.rationale, actor=actor)
    return envelope(ReviewRead.of(r), f"{r.display_number} recorded (version {r.version})")


@router.get("/cases/{case_id}/reviews", response_model=SuccessEnvelope[list[ReviewRead]], responses=_CASE_404,
            summary="A case's reviews, newest first; current=true keeps only the latest version per subject")
def case_reviews(case_id: uuid.UUID, current: bool = Query(default=False), session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    return envelope([ReviewRead.of(r) for r in ReviewService.list_reviews(session, case_id, current_only=current)], "Reviews retrieved successfully")


class ReportCreate(BaseModel):
    kind: Literal["DRAFT", "FINAL"] = "DRAFT"


class ReportRead(BaseModel):
    report_id: uuid.UUID
    report_number: str
    case_id: uuid.UUID
    version: int
    kind: str
    state: str
    job_id: uuid.UUID | None
    json_sha256: str | None
    pdf_sha256: str | None
    summary: dict
    error: str | None
    requested_by: str
    created_at: datetime
    generated_at: datetime | None

    @classmethod
    def of(cls, r: Report) -> "ReportRead":
        return cls(report_id=r.id, report_number=r.display_number, case_id=r.case_id, version=r.version, kind=r.kind, state=r.state,
                   job_id=r.job_id, json_sha256=r.json_sha256, pdf_sha256=r.pdf_sha256, summary=r.summary or {}, error=r.error,
                   requested_by=r.requested_by, created_at=r.created_at, generated_at=r.generated_at)


@router.post("/cases/{case_id}/reports", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessEnvelope[ReportRead],
             responses=_CASE_404 | {409: {"model": ErrorEnvelope, "description": "CONCLUSION_REQUIRED or CASE_ARCHIVED"}},
             summary="Request a report version; a worker generates its JSON and PDF")
def create_report(case_id: uuid.UUID, body: ReportCreate, session: Session = Depends(get_db_session), actor: str = Depends(get_actor),
                  settings: Settings = Depends(get_settings_dependency)):
    report, job = ReportService.request(session, case_id, body.kind, actor, settings)
    return envelope(ReportRead.of(report), f"{report.display_number} queued as {job.display_number}")


@router.get("/cases/{case_id}/reports", response_model=SuccessEnvelope[list[ReportRead]], responses=_CASE_404, summary="A case's report versions")
def case_reports(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    return envelope([ReportRead.of(r) for r in ReportService.list_reports(session, case_id)], "Reports retrieved successfully")


@router.get("/reports/{report_id}", response_model=SuccessEnvelope[ReportRead],
            responses={404: {"model": ErrorEnvelope, "description": "REPORT_NOT_FOUND"}}, summary="Report detail")
def report_detail(report_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(ReportRead.of(ReportService.get_report(session, report_id)), "Report retrieved successfully")


@router.get("/reports/{report_id}/download", responses={404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope, "description": "REPORT_NOT_READY"}},
            summary="Download a generated report file (PDF or JSON), with its SHA-256 in X-Report-SHA256")
def download_report(report_id: uuid.UUID, format: Literal["pdf", "json"] = "pdf", session: Session = Depends(get_db_session),
                    storage: LocalStorage = Depends(get_storage)):
    r = ReportService.get_report(session, report_id)
    if r.state != "GENERATED":
        raise NextronError(409, ErrorCode.REPORT_NOT_READY, f"The report is {r.state.lower()}, not generated")
    key, digest = (r.pdf_key, r.pdf_sha256) if format == "pdf" else (r.json_key, r.json_sha256)
    path = storage.report_path(key)
    if not path.is_file():
        raise NextronError(404, ErrorCode.ARTIFACT_FILE_MISSING, "The report file is missing from storage")
    name = f"NEXTRON-{r.display_number}-v{r.version}.{format}"
    return FileResponse(path, media_type="application/pdf" if format == "pdf" else "application/json", filename=name,
                        headers={"X-Report-SHA256": digest, "X-Content-Type-Options": "nosniff"})
