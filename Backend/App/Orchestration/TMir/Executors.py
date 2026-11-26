"""Module executors: how T-MIR runs one module for one scope.

An executor has three parts, so the slow work never holds a database transaction and a crash can never
leave half a result:

  inputs(ctx)               the pinned references the run will read (they define the input fingerprint);
  run(ctx)                  the computation; no database writes; T-MIR runs it under the module timeout;
  record(session, ctx, out) writes the module's own domain records into T-MIR's completing transaction
                            and returns the findings for the result envelope.

Only modules built so far have an executor. Every other T-MIR module that a plan decides to run ends
UNAVAILABLE with reason MODULE_NOT_IMPLEMENTED: an honest "not built yet", never a pretend result.

The media engines (NEX-IMG, NEX-VID, NEX-AUD, NEX-PRV) share EngineExecutor: run() calls the engine on the
preserved original and writes its derived artifacts to protected storage (write-once, read-only); record()
adds their ArtifactRecord rows (with SHA-256) in the completing transaction and returns the findings. A crash
between the two leaves unreferenced derived files only, never a record without its file.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Contracts.Artifacts import ArtifactRef, InputKind, InputReference
from Backend.App.Contracts.ExecutionStates import ExecutionState, FailureReason
from Backend.App.Contracts.Findings import Assertion, Finding
from Backend.App.Contracts.ModuleResult import ModuleError
from Backend.App.Modules.Engine import EngineOutput
from Backend.App.Modules.NexAud import AudioAnalyzer
from Backend.App.Modules.NexImg import ImageAnalyzer
from Backend.App.Modules.NexMet import MetadataExtractor
from Backend.App.Modules.NexPrv import C2paAnalyzer
from Backend.App.Modules.NexVid import VideoAnalyzer
from Backend.App.Modules.NexMet import Service as MetadataService
from Backend.App.Storage.StorageInterface import EvidenceStorage, derived_key
from Database.PostgreSQL.Models import AnalysisJob, ArtifactRecord, Evidence

NOT_IMPLEMENTED = "MODULE_NOT_IMPLEMENTED"


@dataclass
class ExecutionContext:
    job: AnalysisJob
    entry: dict[str, Any]
    evidence: Evidence | None           # for evidence-scoped entries
    run_evidence: list[Evidence]        # everything the run covers
    upstream_results: dict[str, list[uuid.UUID]]  # module_id -> result IDs this execution may read
    settings: Settings
    storage: EvidenceStorage
    actor: str
    execution_id: uuid.UUID | None = None  # set by the runner once the execution is opened


@dataclass
class Outcome:
    status: ExecutionState
    reason: str | None = None
    detail: str | None = None
    data: Any = None                    # passed from run() to record()
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[ModuleError] = field(default_factory=list)
    tool_versions: dict[str, str] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)  # filled by record(), listed in the envelope


class ModuleExecutor(Protocol):
    module_id: str
    version: str

    def parameters(self, ctx: ExecutionContext) -> dict[str, Any]: ...
    def inputs(self, ctx: ExecutionContext) -> list[InputReference]: ...
    def run(self, ctx: ExecutionContext) -> Outcome: ...
    def record(self, session: Session, ctx: ExecutionContext, outcome: Outcome) -> list[Finding]: ...


def evidence_input(evidence: Evidence) -> InputReference:
    return InputReference(kind=InputKind.EVIDENCE, id=evidence.id, sha256=evidence.sha256)


def default_inputs(ctx: ExecutionContext) -> list[InputReference]:
    """The evidence the entry covers plus the upstream results it may read."""
    covered = [ctx.evidence] if ctx.evidence is not None else ctx.run_evidence
    refs = [evidence_input(e) for e in covered]
    for module_id, result_ids in sorted(ctx.upstream_results.items()):
        refs += [InputReference(kind=InputKind.MODULE_RESULT, id=r, module_id=module_id) for r in result_ids]
    return refs


class MetadataExecutor:
    """NEX-MET: container, stream and embedded metadata of the preserved original (Pillow / FFprobe)."""

    module_id = "NEX-MET"
    version = MetadataExtractor.EXTRACTOR_REVISION

    def parameters(self, ctx: ExecutionContext) -> dict[str, Any]:
        return {}  # the probe timeout bounds the run; it does not change what is computed

    def inputs(self, ctx: ExecutionContext) -> list[InputReference]:
        return [evidence_input(ctx.evidence)]

    def run(self, ctx: ExecutionContext) -> Outcome:
        result = MetadataService.extract(
            ctx.storage, ctx.evidence, ffprobe=ctx.settings.FFPROBE_PATH, timeout_seconds=ctx.settings.MEDIA_PROBE_TIMEOUT_SECONDS
        )
        tools = {result.extractor: result.extractor_version}
        if result.status == "EXTRACTED":
            return Outcome(ExecutionState.COMPLETED, data=result, tool_versions=tools)
        if result.status == "UNAVAILABLE":
            return Outcome(ExecutionState.UNAVAILABLE, FailureReason.TOOL_UNAVAILABLE.value, result.error, data=result, tool_versions=tools)
        return Outcome(ExecutionState.FAILED, FailureReason.ERROR.value, result.error, data=result, tool_versions=tools,
                       errors=[ModuleError(code="EXTRACTION_FAILED", message=(result.error or "Metadata extraction failed")[:2000])])

    def record(self, session: Session, ctx: ExecutionContext, outcome: Outcome) -> list[Finding]:
        row = MetadataService.record(session, ctx.evidence, outcome.data, ctx.actor, job_id=str(ctx.job.id))
        if outcome.status is not ExecutionState.COMPLETED:
            return []
        summary = outcome.data.summary or {}
        return [Finding(
            module_id=self.module_id,
            evidence_ids=[ctx.evidence.id],
            assertion=Assertion.OBSERVATION,
            finding_type="METADATA_RECORDED",
            title="Container and embedded metadata recorded",
            description="Fields read from the preserved original. Embedded timestamps are claims made by the file, "
                        "not evidence of when the content was created.",
            measurement={"metadata_id": str(row.id), "extractor": row.extractor, "extractor_version": row.extractor_version,
                         "summary": summary},
        )]


class EngineExecutor:
    """A media engine over the preserved original: (path, evidence_id, ctx) -> EngineOutput."""

    def __init__(self, module_id: str, version: str, parameters: dict[str, Any], engine):
        self.module_id, self.version, self._parameters, self._engine = module_id, version, parameters, engine

    def parameters(self, ctx: ExecutionContext) -> dict[str, Any]:
        return dict(self._parameters)

    def inputs(self, ctx: ExecutionContext) -> list[InputReference]:
        return [evidence_input(ctx.evidence)]

    def run(self, ctx: ExecutionContext) -> Outcome:
        path = ctx.storage.local_path(ctx.evidence.storage_key)
        if path is None or not path.is_file():
            return Outcome(ExecutionState.FAILED, FailureReason.INVALID_INPUT.value, "The preserved original is not readable",
                           errors=[ModuleError(code="ORIGINAL_MISSING", message="The preserved original is not readable; run an integrity check")])
        result: EngineOutput = self._engine(path, ctx)
        for a in result.artifacts:  # outside any transaction; write-once
            ctx.storage.write_derived(derived_key(ctx.evidence.case_id, ctx.evidence.id, a.artifact_id, a.extension), a.data)
        errors = [ModuleError(code="ENGINE_FAILED", message=result.error[:2000])] if result.status is ExecutionState.FAILED else []
        return Outcome(result.status, result.reason, result.detail, data=result, limitations=result.limitations,
                       warnings=result.warnings, errors=errors, tool_versions=result.tool_versions)

    def record(self, session: Session, ctx: ExecutionContext, outcome: Outcome) -> list[Finding]:
        result: EngineOutput = outcome.data
        for a in result.artifacts:
            digest = hashlib.sha256(a.data).hexdigest()
            session.add(ArtifactRecord(
                id=a.artifact_id, case_id=ctx.evidence.case_id, evidence_id=ctx.evidence.id, execution_id=ctx.execution_id, kind=a.kind.value,
                storage_key=derived_key(ctx.evidence.case_id, ctx.evidence.id, a.artifact_id, a.extension), sha256=digest,
                size_bytes=len(a.data), mime_type=a.mime_type, attributes=a.attributes,
            ))
            outcome.artifacts.append(ArtifactRef(artifact_id=a.artifact_id, kind=a.kind, sha256=digest, size_bytes=len(a.data),
                                                 mime_type=a.mime_type, evidence_id=ctx.evidence.id, attributes=a.attributes))
        session.flush()
        return result.findings if outcome.status.produced_output else []


def _engine_error(fn):
    """Engines raise on undecodable input; that is the module's FAILED result, not a worker error."""
    def run(path, ctx):
        try:
            return fn(path, ctx)
        except Exception as exc:  # noqa: BLE001 — reported on the execution, with the exception type
            return EngineOutput(ExecutionState.FAILED, FailureReason.ERROR.value, f"{type(exc).__name__}: {exc}"[:500], error=f"{type(exc).__name__}: {exc}")
    return run


EXECUTORS: dict[str, ModuleExecutor] = {e.module_id: e for e in (
    MetadataExecutor(),
    EngineExecutor("NEX-IMG", ImageAnalyzer.VERSION, ImageAnalyzer.PARAMETERS,
                   _engine_error(lambda path, ctx: ImageAnalyzer.analyze(path, ctx.evidence.id))),
    EngineExecutor("NEX-VID", VideoAnalyzer.VERSION, VideoAnalyzer.PARAMETERS,
                   _engine_error(lambda path, ctx: VideoAnalyzer.analyze(path, ctx.evidence.id, settings=ctx.settings))),
    EngineExecutor("NEX-AUD", AudioAnalyzer.VERSION, AudioAnalyzer.PARAMETERS,
                   _engine_error(lambda path, ctx: AudioAnalyzer.analyze(path, ctx.evidence.id, settings=ctx.settings))),
    EngineExecutor("NEX-PRV", C2paAnalyzer.VERSION, C2paAnalyzer.PARAMETERS,
                   _engine_error(lambda path, ctx: C2paAnalyzer.analyze(path, ctx.evidence.id, mime_type=ctx.evidence.mime_type))),
)}
