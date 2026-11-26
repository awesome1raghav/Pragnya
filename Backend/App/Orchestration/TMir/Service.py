"""T-MIR service for the API: start runs, read runs, executions, results and per-evidence analysis.

Nothing here runs a module. Starting a run queues an INVESTIGATION_RUN job; a worker plans and executes it.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Contracts.ExecutionStates import JobType
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexEvd.Service import get_evidence
from Backend.App.Orchestration.TMir import DependencyRegistry as R
from Backend.App.Orchestration.TMir import Planner
from Backend.App.Orchestration.TMir.Schemas import (
    ArtifactRead,
    EvidenceAnalysis,
    EvidenceModuleResult,
    ModuleResults,
    ExecutionRead,
    FindingRead,
    JobRead,
    ModuleAnalysis,
    PlanEntryRead,
    Reproducibility,
    ResultRead,
    RunRead,
)
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisFinding, AnalysisJob, AnalysisResult, ArtifactRecord, Case, Evidence

EVIDENCE_MODULES = tuple(m for m in R.topological_order() if R.spec(m).owner is R.Owner.TMIR and R.spec(m).scope is R.Scope.EVIDENCE)


def start_run(session: Session, case_id: uuid.UUID, actor: str, settings: Settings, *, evidence_id: uuid.UUID | None = None,
              trigger: str = "operator") -> AnalysisJob:
    case = get_case(session, case_id)
    Lifecycle.ensure_writable(case)
    if evidence_id is not None:
        evidence = get_evidence(session, evidence_id)
        if evidence.case_id != case_id:
            raise NextronError(404, ErrorCode.EVIDENCE_NOT_FOUND, "The evidence does not belong to this case")
    elif not session.scalar(select(func.count()).where(Evidence.case_id == case_id)):
        raise NextronError(409, ErrorCode.NO_EVIDENCE, "The case has no evidence to analyse yet")
    job = JobService.enqueue(session, job_type=JobType.INVESTIGATION_RUN, case_id=case_id, evidence_id=evidence_id,
                             requested_by=actor, settings=settings, parameters={"trigger": trigger})
    session.commit()
    session.refresh(job)
    return job


# ── jobs ─────────────────────────────────────────────────────────────────────────────────────

def _job_rows(query):
    return (query.add_columns(Case.case_number, Evidence.evidence_number)
            .join(Case, Case.id == AnalysisJob.case_id).outerjoin(Evidence, Evidence.id == AnalysisJob.evidence_id))


def list_jobs(session: Session, *, page: int, page_size: int, state: str | None = None, case_id: uuid.UUID | None = None,
              evidence_id: uuid.UUID | None = None, job_type: str | None = None, active: bool | None = None) -> tuple[list[JobRead], int]:
    conditions = []
    if state:
        conditions.append(AnalysisJob.state == state)
    if active is True:
        conditions.append(AnalysisJob.state.in_(("QUEUED", "RUNNING")))
    if case_id:
        conditions.append(AnalysisJob.case_id == case_id)
    if evidence_id:
        conditions.append(AnalysisJob.evidence_id == evidence_id)
    if job_type:
        conditions.append(AnalysisJob.job_type == job_type)
    total = session.scalar(select(func.count()).select_from(AnalysisJob).where(*conditions)) or 0
    rows = session.execute(
        _job_rows(select(AnalysisJob)).where(*conditions).order_by(AnalysisJob.job_number.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [JobRead.of(job, cn, en) for job, cn, en in rows], total


def job_read(session: Session, job_id: uuid.UUID) -> JobRead:
    row = session.execute(_job_rows(select(AnalysisJob)).where(AnalysisJob.id == job_id)).first()
    if row is None:
        raise NextronError(404, ErrorCode.JOB_NOT_FOUND, "The requested job does not exist")
    return JobRead.of(*row)


def _result_ids(session: Session, execution_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not execution_ids:
        return {}
    rows = session.execute(select(AnalysisResult.execution_id, AnalysisResult.id).where(AnalysisResult.execution_id.in_(execution_ids)))
    return dict(rows.all())


def run_detail(session: Session, job_id: uuid.UUID) -> RunRead:
    job = job_read(session, job_id)
    if job.job_type != JobType.INVESTIGATION_RUN.value:
        raise NextronError(404, ErrorCode.RUN_NOT_FOUND, "The job is not an investigation run")
    plan = session.scalar(select(AnalysisJob.plan).where(AnalysisJob.id == job_id))
    executions = list(session.scalars(
        select(AnalysisExecution).where(AnalysisExecution.job_id == job_id).order_by(AnalysisExecution.created_at, AnalysisExecution.attempt)
    ))
    results = _result_ids(session, [e.id for e in executions])
    return RunRead(
        **job.model_dump(),
        plan=[PlanEntryRead.of(e) for e in (plan or {}).get("entries", [])],
        executions=[ExecutionRead.of(e, results.get(e.id)) for e in executions],
    )


# ── results ──────────────────────────────────────────────────────────────────────────────────

def get_result(session: Session, result_id: uuid.UUID) -> AnalysisResult:
    result = session.get(AnalysisResult, result_id)
    if result is None:
        raise NextronError(404, ErrorCode.RESULT_NOT_FOUND, "The requested analysis result does not exist")
    return result


def reproducibility(session: Session, result_id: uuid.UUID) -> Reproducibility:
    result = get_result(session, result_id)
    ex = session.get(AnalysisExecution, result.execution_id)
    return Reproducibility(result_id=result.id, module_id=ex.module_id, module_version=ex.module_version,
                           input_fingerprint=ex.input_fingerprint, parameters=ex.parameters or {},
                           tool_versions=ex.tool_versions or {}, input_references=result.envelope.get("input_references", []))


def _artifact(a: ArtifactRecord) -> ArtifactRead:
    return ArtifactRead(artifact_id=a.id, kind=a.kind, mime_type=a.mime_type, sha256=a.sha256, size_bytes=a.size_bytes,
                        evidence_id=a.evidence_id, execution_id=a.execution_id, attributes=a.attributes or {}, created_at=a.created_at)


def artifacts(session: Session, result_id: uuid.UUID) -> list[ArtifactRead]:
    result = get_result(session, result_id)
    rows = session.scalars(select(ArtifactRecord).where(ArtifactRecord.execution_id == result.execution_id).order_by(ArtifactRecord.created_at))
    return [_artifact(a) for a in rows]


def get_artifact(session: Session, artifact_id: uuid.UUID) -> ArtifactRecord:
    artifact = session.get(ArtifactRecord, artifact_id)
    if artifact is None:
        raise NextronError(404, ErrorCode.ARTIFACT_NOT_FOUND, "The requested artifact does not exist")
    return artifact


def module_results(session: Session, case_id: uuid.UUID, module_id: str) -> ModuleResults:
    """For each evidence item in the case: this module's latest execution and current result, findings, artifacts."""
    if module_id not in EVIDENCE_MODULES:
        raise NextronError(404, ErrorCode.UNKNOWN_MODULE, "Not an evidence-scoped T-MIR module", {"modules": list(EVIDENCE_MODULES)})
    get_case(session, case_id)
    items = list(session.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.evidence_number)))
    scopes = [str(e.id) for e in items]
    latest = {e.scope_ref: e for e in session.scalars(
        select(AnalysisExecution).ext(distinct_on(AnalysisExecution.scope_ref))
        .where(AnalysisExecution.module_id == module_id, AnalysisExecution.scope_ref.in_(scopes))
        .order_by(AnalysisExecution.scope_ref, AnalysisExecution.created_at.desc(), AnalysisExecution.attempt.desc()))} if scopes else {}
    current = {ex.scope_ref: (res, ex) for res, ex in session.execute(
        select(AnalysisResult, AnalysisExecution).ext(distinct_on(AnalysisExecution.scope_ref))
        .join(AnalysisExecution, AnalysisExecution.id == AnalysisResult.execution_id)
        .where(AnalysisResult.module_id == module_id, AnalysisExecution.scope_ref.in_(scopes),
               AnalysisResult.status.in_(("COMPLETED", "PARTIALLY_COMPLETED")), AnalysisResult.superseded_at.is_(None))
        .order_by(AnalysisExecution.scope_ref, AnalysisResult.created_at.desc())).all()} if scopes else {}
    results = _result_ids(session, [e.id for e in latest.values()])
    out = []
    for e in items:
        ref = str(e.id)
        res, ex = current.get(ref, (None, None))
        findings = session.scalars(select(AnalysisFinding).where(AnalysisFinding.result_id == res.id).order_by(AnalysisFinding.created_at)).all() if res else []
        arts = session.scalars(select(ArtifactRecord).where(ArtifactRecord.execution_id == ex.id).order_by(ArtifactRecord.created_at)).all() if ex else []
        env = res.envelope if res else {}
        out.append(EvidenceModuleResult(
            evidence_id=e.id, evidence_number=e.display_number, filename=e.original_filename, media_type=e.media_type,
            applicable=R.applies_to(module_id, Planner.facts(e)),
            latest=ExecutionRead.of(latest[ref], results.get(latest[ref].id)) if ref in latest else None,
            result_id=res.id if res else None, status=res.status if res else None, status_reason=env.get("status_reason"),
            limitations=env.get("limitations", []), tool_versions=env.get("tool_versions", {}),
            findings=[FindingRead.of(f) for f in findings], artifacts=[_artifact(a) for a in arts],
        ))
    return ModuleResults(module_id=module_id, module_name=R.spec(module_id).name, case_id=case_id, evidence=out)


def evidence_analysis(session: Session, evidence_id: uuid.UUID) -> EvidenceAnalysis:
    evidence = get_evidence(session, evidence_id)
    jobs, _ = list_jobs(session, page=1, page_size=10, evidence_id=evidence_id)
    scope = str(evidence_id)
    latest_rows = session.execute(
        select(AnalysisExecution).ext(distinct_on(AnalysisExecution.module_id))
        .where(AnalysisExecution.scope_ref == scope)
        .order_by(AnalysisExecution.module_id, AnalysisExecution.created_at.desc(), AnalysisExecution.attempt.desc())
    ).scalars().all()
    latest = {e.module_id: e for e in latest_rows}
    current_rows = session.execute(
        select(AnalysisResult.module_id, AnalysisResult.id).ext(distinct_on(AnalysisResult.module_id))
        .join(AnalysisExecution, AnalysisExecution.id == AnalysisResult.execution_id)
        .where(AnalysisExecution.scope_ref == scope, AnalysisResult.status.in_(("COMPLETED", "PARTIALLY_COMPLETED")),
               AnalysisResult.superseded_at.is_(None))
        .order_by(AnalysisResult.module_id, AnalysisResult.created_at.desc())
    ).all()
    current = dict(current_rows)
    results = _result_ids(session, [e.id for e in latest.values()])
    facts = Planner.facts(evidence)
    modules = [
        ModuleAnalysis(module_id=m, module_name=R.spec(m).name, group=R.spec(m).group, applicable=R.applies_to(m, facts),
                       latest=ExecutionRead.of(latest[m], results.get(latest[m].id)) if m in latest else None,
                       current_result_id=current.get(m))
        for m in EVIDENCE_MODULES
    ]
    findings = session.scalars(
        select(AnalysisFinding).join(AnalysisResult, AnalysisResult.id == AnalysisFinding.result_id)
        .where(AnalysisFinding.evidence_ids.contains([evidence_id]), AnalysisResult.superseded_at.is_(None))
        .order_by(AnalysisFinding.created_at.desc()).limit(200)
    ).all()
    current_executions = session.scalars(select(AnalysisResult.execution_id).where(AnalysisResult.id.in_(list(current.values())))).all() if current else []
    arts = session.scalars(select(ArtifactRecord).where(ArtifactRecord.execution_id.in_(current_executions))
                           .order_by(ArtifactRecord.created_at)).all() if current_executions else []
    return EvidenceAnalysis(evidence_id=evidence_id, latest_job=jobs[0] if jobs else None, jobs=jobs, modules=modules,
                            findings=[FindingRead.of(f) for f in findings], artifacts=[_artifact(a) for a in arts])
