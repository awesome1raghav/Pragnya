"""API schemas for jobs, T-MIR runs, module executions, results and evidence analysis."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from Backend.App.Orchestration.TMir import DependencyRegistry as R
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisFinding, AnalysisJob, AnalysisResult


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    return int((end - start).total_seconds() * 1000) if start and end else None


class JobRead(BaseModel):
    job_id: uuid.UUID
    job_number: str = Field(examples=["JOB-0001"])
    job_type: str
    case_id: uuid.UUID
    case_number: str | None = None
    evidence_id: uuid.UUID | None
    evidence_number: str | None = None
    state: str
    priority: int
    requested_by: str
    parameters: dict[str, Any]
    progress: dict[str, Any] | None = Field(description="Measured progress: planned and finished module entries, by state")
    attempt: int
    max_attempts: int
    cancel_requested: bool
    error: dict[str, Any] | None
    worker_id: str | None = Field(description="The worker holding the lease while RUNNING")
    heartbeat_at: datetime | None
    available_at: datetime
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None

    @classmethod
    def of(cls, job: AnalysisJob, case_number: int | None = None, evidence_number: int | None = None) -> "JobRead":
        return cls(
            job_id=job.id, job_number=job.display_number, job_type=job.job_type, case_id=job.case_id,
            case_number=f"CASE-{case_number:04d}" if case_number else None, evidence_id=job.evidence_id,
            evidence_number=f"EVD-{evidence_number:04d}" if evidence_number else None, state=job.state, priority=job.priority,
            requested_by=job.requested_by, parameters=job.parameters or {}, progress=job.progress, attempt=job.attempt,
            max_attempts=job.max_attempts, cancel_requested=job.cancel_requested, error=job.error, worker_id=job.lease_owner,
            heartbeat_at=job.heartbeat_at, available_at=job.available_at, created_at=job.created_at, started_at=job.started_at,
            finished_at=job.finished_at, duration_ms=_duration_ms(job.started_at, job.finished_at),
        )


class PlanEntryRead(BaseModel):
    key: str
    module_id: str
    module_name: str
    group: str
    scope_kind: str
    scope_ref: str
    evidence_id: uuid.UUID | None
    applicable: bool
    state: str
    reason: str | None
    detail: str | None
    execution_id: uuid.UUID | None
    result_id: uuid.UUID | None
    reused_from_job_id: uuid.UUID | None
    interrupted_attempts: list[uuid.UUID]
    limitations: list[str]

    @classmethod
    def of(cls, entry: dict[str, Any]) -> "PlanEntryRead":
        m = R.spec(entry["module_id"])
        return cls(
            key=entry["key"], module_id=m.module_id, module_name=m.name, group=m.group, scope_kind=entry["scope_kind"],
            scope_ref=entry["scope_ref"], evidence_id=entry["evidence_id"], applicable=entry["applicable"], state=entry["state"],
            reason=entry["reason"], detail=entry["detail"], execution_id=entry["execution_id"] or entry.get("running_execution_id"),
            result_id=entry["result_id"], reused_from_job_id=entry["reused_from_job_id"],
            interrupted_attempts=entry.get("attempts", []), limitations=entry.get("limitations", []),
        )


class ExecutionRead(BaseModel):
    execution_id: uuid.UUID
    job_id: uuid.UUID
    module_id: str
    module_name: str
    scope_kind: str
    scope_ref: str
    attempt: int
    state: str
    state_reason: str | None
    state_detail: str | None
    input_fingerprint: str
    module_version: str
    tool_versions: dict[str, Any]
    error: dict[str, Any] | None
    result_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None

    @classmethod
    def of(cls, ex: AnalysisExecution, result_id: uuid.UUID | None) -> "ExecutionRead":
        return cls(
            execution_id=ex.id, job_id=ex.job_id, module_id=ex.module_id, module_name=R.spec(ex.module_id).name,
            scope_kind=ex.scope_kind, scope_ref=ex.scope_ref, attempt=ex.attempt, state=ex.state, state_reason=ex.state_reason,
            state_detail=ex.state_detail, input_fingerprint=ex.input_fingerprint, module_version=ex.module_version,
            tool_versions=ex.tool_versions or {}, error=ex.error, result_id=result_id, created_at=ex.created_at,
            started_at=ex.started_at, finished_at=ex.finished_at, duration_ms=ex.duration_ms,
        )


class RunRead(JobRead):
    plan: list[PlanEntryRead] = Field(description="Every planned module entry, including those skipped and why")
    executions: list[ExecutionRead] = Field(description="Every execution this job wrote, all attempts")


class ResultRead(BaseModel):
    result_id: uuid.UUID
    execution_id: uuid.UUID
    job_id: uuid.UUID
    case_id: uuid.UUID
    module_id: str
    module_name: str
    status: str
    schema_version: str
    envelope: dict[str, Any] = Field(description="The module result envelope (schema 1.0), exactly as stored")
    created_at: datetime
    superseded_at: datetime | None

    @classmethod
    def of(cls, r: AnalysisResult) -> "ResultRead":
        return cls(
            result_id=r.id, execution_id=r.execution_id, job_id=r.job_id, case_id=r.case_id, module_id=r.module_id,
            module_name=R.spec(r.module_id).name, status=r.status, schema_version=r.schema_version, envelope=r.envelope,
            created_at=r.created_at, superseded_at=r.superseded_at,
        )


class Reproducibility(BaseModel):
    result_id: uuid.UUID
    module_id: str
    module_version: str
    input_fingerprint: str
    parameters: dict[str, Any]
    tool_versions: dict[str, Any]
    input_references: list[dict[str, Any]]
    note: str = ("Running this module version with these parameters on these pinned inputs computes the same fingerprint; "
                 "T-MIR then reuses this result instead of recomputing it.")


class FindingRead(BaseModel):
    finding_id: uuid.UUID
    result_id: uuid.UUID
    module_id: str
    module_name: str
    evidence_ids: list[uuid.UUID]
    assertion: str
    finding_type: str
    title: str
    description: str | None
    score: float | None
    score_kind: str | None
    confidence: float | None
    confidence_basis: str | None
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def of(cls, f: AnalysisFinding) -> "FindingRead":
        return cls(
            finding_id=f.id, result_id=f.result_id, module_id=f.module_id, module_name=R.spec(f.module_id).name,
            evidence_ids=list(f.evidence_ids), assertion=f.assertion, finding_type=f.finding_type, title=f.title,
            description=f.description, score=f.score, score_kind=f.score_kind, confidence=f.confidence,
            confidence_basis=f.confidence_basis, payload=f.payload, created_at=f.created_at,
        )


class ModuleAnalysis(BaseModel):
    module_id: str
    module_name: str
    group: str
    applicable: bool
    latest: ExecutionRead | None = Field(description="The most recent execution of this module for this evidence")
    current_result_id: uuid.UUID | None = Field(description="The newest non-superseded completed result, if any")


class EvidenceAnalysis(BaseModel):
    evidence_id: uuid.UUID
    latest_job: JobRead | None
    jobs: list[JobRead]
    modules: list[ModuleAnalysis] = Field(description="Every evidence-scoped T-MIR module, in dependency order")
    findings: list[FindingRead] = Field(description="Findings about this evidence from current (non-superseded) results")
    artifacts: list["ArtifactRead"] = Field(default_factory=list, description="Derived artifacts of the current results")


class ArtifactRead(BaseModel):
    artifact_id: uuid.UUID
    kind: str
    mime_type: str
    sha256: str
    size_bytes: int
    evidence_id: uuid.UUID | None
    execution_id: uuid.UUID | None
    attributes: dict[str, Any]
    created_at: datetime


class EvidenceModuleResult(BaseModel):
    """One evidence item's current result from one module, with its findings and artifacts."""

    evidence_id: uuid.UUID
    evidence_number: str
    filename: str
    media_type: str
    applicable: bool
    latest: ExecutionRead | None
    result_id: uuid.UUID | None
    status: str | None
    status_reason: str | None
    limitations: list[str]
    tool_versions: dict[str, Any]
    findings: list[FindingRead]
    artifacts: list[ArtifactRead]


class ModuleResults(BaseModel):
    module_id: str
    module_name: str
    case_id: uuid.UUID
    evidence: list[EvidenceModuleResult]


EvidenceAnalysis.model_rebuild()


class StartRun(BaseModel):
    evidence_id: uuid.UUID | None = Field(default=None, description="Analyse one evidence item; omit to analyse every item in the case")
