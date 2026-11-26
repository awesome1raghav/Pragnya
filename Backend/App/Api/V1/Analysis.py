"""Analysis and T-MIR run APIs: start runs (202), read plans, executions, result envelopes and findings."""

import uuid

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Dependencies import get_actor, get_db_session, get_settings_dependency
from Backend.App.Modules.NexEvd.Service import get_evidence
from Backend.App.Orchestration.TMir import Service as TMirService
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_storage
from Backend.App.Orchestration.TMir.Schemas import ArtifactRead, EvidenceAnalysis, JobRead, ModuleResults, Reproducibility, ResultRead, RunRead, StartRun
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated
from Backend.App.Contracts.ExecutionStates import JobType
from Backend.App.Modules.NexCm.Service import get_case

router = APIRouter(tags=["Analysis and T-MIR"])

_ACCEPTED = {
    404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND or EVIDENCE_NOT_FOUND"},
    409: {"model": ErrorEnvelope, "description": "CASE_ARCHIVED or NO_EVIDENCE"},
}
_RESULT_404 = {404: {"model": ErrorEnvelope, "description": "RESULT_NOT_FOUND"}}


@router.post("/cases/{case_id}/runs", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessEnvelope[JobRead],
             responses=_ACCEPTED, summary="Start a T-MIR investigation run (queued; a worker executes it)")
def start_run(
    case_id: uuid.UUID,
    body: StartRun = Body(default_factory=StartRun),
    session: Session = Depends(get_db_session),
    actor: str = Depends(get_actor),
    settings: Settings = Depends(get_settings_dependency),
):
    job = TMirService.start_run(session, case_id, actor, settings, evidence_id=body.evidence_id)
    return envelope(TMirService.job_read(session, job.id), f"Queued {job.display_number}")


@router.get("/cases/{case_id}/runs", response_model=PaginatedEnvelope[JobRead], responses={404: {"model": ErrorEnvelope}},
            summary="A case's investigation runs, newest first")
def list_runs(
    case_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    get_case(session, case_id)
    items, total = TMirService.list_jobs(session, page=page, page_size=page_size, case_id=case_id, job_type=JobType.INVESTIGATION_RUN.value)
    return paginated(items, "Runs retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/runs/{job_id}", response_model=SuccessEnvelope[RunRead], responses={404: {"model": ErrorEnvelope, "description": "JOB_NOT_FOUND"}},
            summary="A run's plan (every module and scope, with reasons) and all its executions")
def run_detail(job_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(TMirService.run_detail(session, job_id), "Run retrieved successfully")


@router.post("/evidence/{evidence_id}/analyze", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessEnvelope[JobRead],
             responses=_ACCEPTED, summary="Analyse one evidence item (queues a T-MIR run for it)")
def analyze_evidence(
    evidence_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    actor: str = Depends(get_actor),
    settings: Settings = Depends(get_settings_dependency),
):
    evidence = get_evidence(session, evidence_id)
    job = TMirService.start_run(session, evidence.case_id, actor, settings, evidence_id=evidence_id)
    return envelope(TMirService.job_read(session, job.id), f"Queued {job.display_number}")


@router.get("/evidence/{evidence_id}/analysis", response_model=SuccessEnvelope[EvidenceAnalysis],
            responses={404: {"model": ErrorEnvelope, "description": "EVIDENCE_NOT_FOUND"}},
            summary="Per-module state, recent runs and current findings for one evidence item")
def evidence_analysis(evidence_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(TMirService.evidence_analysis(session, evidence_id), "Analysis retrieved successfully")


@router.get("/analyses/{result_id}", response_model=SuccessEnvelope[ResultRead], responses=_RESULT_404,
            summary="A module result envelope")
def analysis_result(result_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(ResultRead.of(TMirService.get_result(session, result_id)), "Result retrieved successfully")


@router.get("/analyses/{result_id}/reproducibility", response_model=SuccessEnvelope[Reproducibility], responses=_RESULT_404,
            summary="Module version, parameters, tool versions and pinned inputs behind a result")
def analysis_reproducibility(result_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(TMirService.reproducibility(session, result_id), "Reproducibility record retrieved successfully")


@router.get("/analyses/{result_id}/artifacts", response_model=SuccessEnvelope[list[ArtifactRead]], responses=_RESULT_404,
            summary="Derived artifacts a result produced (heatmaps, frame sets, audio tracks, signatures)")
def analysis_artifacts(result_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(TMirService.artifacts(session, result_id), "Artifacts retrieved successfully")


# Derived artifacts are served like evidence previews: inert, no sniffing, no scripts.
_ARTIFACT_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; sandbox",
    "Cache-Control": "private, max-age=3600, immutable",
}


@router.get("/artifacts/{artifact_id}", response_class=FileResponse,
            responses={200: {"description": "The artifact bytes, with X-Artifact-SHA256"}, 404: {"model": ErrorEnvelope, "description": "ARTIFACT_NOT_FOUND"},
                       410: {"model": ErrorEnvelope, "description": "ARTIFACT_FILE_MISSING"}},
            summary="A derived artifact's bytes (immutable; its SHA-256 is in the header)")
def artifact_content(artifact_id: uuid.UUID, session: Session = Depends(get_db_session), storage: LocalStorage = Depends(get_storage)):
    artifact = TMirService.get_artifact(session, artifact_id)
    path = storage.derived_path(artifact.storage_key)
    if not path.is_file():
        raise NextronError(410, ErrorCode.ARTIFACT_FILE_MISSING, "The artifact file is missing from storage")
    return FileResponse(path, media_type=artifact.mime_type, content_disposition_type="inline",
                        filename=f"{artifact.kind.lower()}-{artifact.id}{path.suffix}", headers=_ARTIFACT_HEADERS | {"X-Artifact-SHA256": artifact.sha256})


@router.get("/cases/{case_id}/modules/{module_id}/results", response_model=SuccessEnvelope[ModuleResults],
            responses={404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND or UNKNOWN_MODULE"}},
            summary="One evidence-scoped module's current results for every evidence item in a case")
def case_module_results(case_id: uuid.UUID, module_id: str, session: Session = Depends(get_db_session)):
    return envelope(TMirService.module_results(session, case_id, module_id), "Module results retrieved successfully")
