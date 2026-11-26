"""The module dependency registry: the single place that knows how the 18 modules connect.

Edges are exactly the solid arrows of the canonical module connectivity flowchart (A1, stored verbatim in
Documentation/Architecture/Module Connectivity.md), each typed:

  REQUIRED     the downstream cannot run without a completed upstream result;
  CONDITIONAL  required only when the upstream applies to the same evidence or pair
               (e.g. IMG -> FPM only for images); its failure becomes a limitation;
  OPTIONAL     used when present; absence or failure becomes a recorded limitation.

T-MIR coordinates the modules whose owner is T-MIR (A1's twelve dotted arrows). `decide()` turns upstream
states into RUN / WAIT / SKIP for one module and one scope. It never waits on something that can no longer
finish, so an inapplicable or failed branch cannot deadlock a run. The registry validates itself on import.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from Backend.App.Contracts.ExecutionStates import ExecutionState, SkipReason


class EdgeKind(StrEnum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    OPTIONAL = "OPTIONAL"


class Owner(StrEnum):
    DOMAIN_SERVICE = "DOMAIN_SERVICE"  # runs inside an API request (case management, acquisition, preservation)
    TMIR = "T-MIR"                     # planned and executed by T-MIR in workers
    SOURCE_JOB = "SOURCE_JOB"          # Source Service job (NEX-SRC)
    HUMAN_REVIEW = "HUMAN_REVIEW"      # investigator decisions (NEX-INV)
    REPORT_JOB = "REPORT_JOB"          # Report Service job (NEX-RPT)


class Scope(StrEnum):
    REQUEST = "REQUEST"    # one API request
    EVIDENCE = "EVIDENCE"  # once per evidence item
    PAIR = "PAIR"          # once per pair of related evidence items
    CASE = "CASE"          # once per investigation
    HUMAN = "HUMAN"
    JOB = "JOB"


class ResourceClass(StrEnum):
    NONE = "NONE"
    LIGHT = "LIGHT"                # metadata, hashing, graph building
    CPU_HEAVY = "CPU_HEAVY"        # decoding, signal processing
    GPU_OPTIONAL = "GPU_OPTIONAL"  # detectors that run on CPU and use a GPU when present


@dataclass(frozen=True)
class EvidenceFacts:
    """What a plan may know about an evidence item before any module runs (from the evidence record)."""

    media_type: str  # IMAGE | VIDEO | AUDIO
    mime_type: str


# Formats NEXTRON accepts that the C2PA SDK reads, confirmed against c2pa-python 0.39 / c2pa-rs 0.92
# (Reader.get_supported_mime_types(); a unit test keeps this list a subset of the installed SDK's).
# Not readable: WebM, Matroska, Ogg, AAC (ADTS), BMP.
C2PA_MIME_TYPES = frozenset({
    "image/jpeg", "image/png", "image/webp", "image/tiff", "image/gif", "image/avif",
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "audio/mp4", "audio/wav", "audio/mpeg", "audio/flac",
})


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    number: int
    name: str
    group: str
    owner: Owner
    scope: Scope
    resource: ResourceClass
    applies_text: str
    applies: Callable[[EvidenceFacts], bool] | None = None  # evidence-scoped modules only
    require_any: tuple[str, ...] = ()  # at least one of these upstreams must produce output
    note: str | None = None


@dataclass(frozen=True)
class Edge:
    upstream: str
    downstream: str
    kind: EdgeKind
    reason: str


GROUPS = (
    "Investigation Foundation",
    "Media Intelligence",
    "Origin & Circulation Intelligence",
    "Correlation Intelligence",
    "Investigation Intelligence",
)
F, M, O, C, I = GROUPS

_any_media = lambda f: f.media_type in ("IMAGE", "VIDEO", "AUDIO")  # noqa: E731

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec("NEX-CM", 1, "Case Management", F, Owner.DOMAIN_SERVICE, Scope.REQUEST, ResourceClass.NONE, "Always: the investigation entry"),
    ModuleSpec("NEX-CAP", 2, "Evidence Acquisition", F, Owner.DOMAIN_SERVICE, Scope.REQUEST, ResourceClass.LIGHT, "When the case accepts evidence (not archived)"),
    ModuleSpec("NEX-EVD", 3, "Evidence Preservation", F, Owner.DOMAIN_SERVICE, Scope.REQUEST, ResourceClass.LIGHT, "After a valid acquisition"),
    ModuleSpec("NEX-MET", 4, "Metadata Intelligence", M, Owner.TMIR, Scope.EVIDENCE, ResourceClass.LIGHT, "Every preserved evidence item", applies=_any_media),
    ModuleSpec("NEX-IMG", 5, "Image Forensics", M, Owner.TMIR, Scope.EVIDENCE, ResourceClass.GPU_OPTIONAL, "Image evidence", applies=lambda f: f.media_type == "IMAGE"),
    ModuleSpec("NEX-VID", 6, "Video Forensics", M, Owner.TMIR, Scope.EVIDENCE, ResourceClass.GPU_OPTIONAL, "Video evidence", applies=lambda f: f.media_type == "VIDEO"),
    ModuleSpec("NEX-AUD", 7, "Audio Forensics", M, Owner.TMIR, Scope.EVIDENCE, ResourceClass.CPU_HEAVY,
               "Audio evidence, or video evidence (the module itself reports NOT_APPLICABLE when a video has no audio stream)",
               applies=lambda f: f.media_type in ("AUDIO", "VIDEO")),
    ModuleSpec("NEX-PRV", 8, "Provenance Intelligence", M, Owner.TMIR, Scope.EVIDENCE, ResourceClass.LIGHT,
               "Formats the C2PA SDK can read (confirmed list); absent credentials are a result, not a skip",
               applies=lambda f: f.mime_type in C2PA_MIME_TYPES),
    ModuleSpec("NEX-SRC", 9, "Source Intelligence", O, Owner.SOURCE_JOB, Scope.JOB, ResourceClass.LIGHT,
               "When an investigator adds or refreshes a source URL (A1 defines no upstream; plan decision D-13)"),
    ModuleSpec("NEX-FPM", 10, "Fingerprint & Similarity", O, Owner.TMIR, Scope.EVIDENCE, ResourceClass.CPU_HEAVY,
               "Every evidence item once at least one media engine produced output for it", applies=_any_media,
               require_any=("NEX-IMG", "NEX-VID", "NEX-AUD"),
               note="Fingerprints are per evidence item; candidate search runs over the case's permitted corpus."),
    ModuleSpec("NEX-MOC", 11, "Media Lineage", O, Owner.TMIR, Scope.CASE, ResourceClass.LIGHT, "When FPM produced fingerprints in the case"),
    ModuleSpec("NEX-ALN", 12, "Temporal Alignment", C, Owner.TMIR, Scope.PAIR, ResourceClass.CPU_HEAVY, "Each comparable pair MOC proposed"),
    ModuleSpec("NEX-TRN", 13, "Transformation Analysis", C, Owner.TMIR, Scope.PAIR, ResourceClass.CPU_HEAVY, "Each pair MOC proposed"),
    ModuleSpec("NEX-CMC", 14, "Cross-Modal Correlation", C, Owner.TMIR, Scope.CASE, ResourceClass.LIGHT,
               "When at least one of IMG, VID, AUD, PRV or TRN produced output", require_any=("NEX-IMG", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-TRN")),
    ModuleSpec("NEX-EGC", 15, "Evidence Graph Construction", I, Owner.TMIR, Scope.CASE, ResourceClass.LIGHT,
               "Always: evidence and case records exist; upstream results add nodes and edges"),
    ModuleSpec("NEX-REC", 16, "Timeline & Reconstruction", I, Owner.TMIR, Scope.CASE, ResourceClass.LIGHT, "When the evidence graph was built"),
    ModuleSpec("NEX-INV", 17, "Review & Decision", I, Owner.HUMAN_REVIEW, Scope.HUMAN, ResourceClass.NONE,
               "Findings can be reviewed as soon as they exist; case conclusions need a completed reconstruction"),
    ModuleSpec("NEX-RPT", 18, "Reporting", I, Owner.REPORT_JOB, Scope.JOB, ResourceClass.LIGHT,
               "On request: DRAFT any time; FINAL only with the review a policy requires"),
)

R, CO, OP = EdgeKind.REQUIRED, EdgeKind.CONDITIONAL, EdgeKind.OPTIONAL
EDGES: tuple[Edge, ...] = (
    Edge("NEX-CM", "NEX-CAP", R, "Evidence is acquired into an existing case"),
    Edge("NEX-CAP", "NEX-EVD", R, "Only validated acquisitions are preserved"),
    Edge("NEX-EVD", "NEX-MET", R, "Analysis reads the preserved original"),
    Edge("NEX-EVD", "NEX-IMG", R, "Analysis reads the preserved original"),
    Edge("NEX-EVD", "NEX-VID", R, "Analysis reads the preserved original"),
    Edge("NEX-EVD", "NEX-AUD", R, "Analysis reads the preserved original"),
    Edge("NEX-EVD", "NEX-PRV", R, "Analysis reads the preserved original"),
    Edge("NEX-MET", "NEX-FPM", OP, "Container facts refine fingerprinting; fingerprints are possible without them"),
    Edge("NEX-IMG", "NEX-FPM", CO, "Image features, when the evidence is an image"),
    Edge("NEX-VID", "NEX-FPM", CO, "Frame and temporal features, when the evidence is a video"),
    Edge("NEX-AUD", "NEX-FPM", CO, "Audio features, when the evidence has audio"),
    Edge("NEX-SRC", "NEX-FPM", OP, "Source-retrieved media widens the searched corpus"),
    Edge("NEX-FPM", "NEX-MOC", R, "Lineage is built from fingerprint candidates"),
    Edge("NEX-SRC", "NEX-MOC", OP, "Source records supply publication times for lineage (A1 only; conflict C-2)"),
    Edge("NEX-MOC", "NEX-ALN", R, "Alignment runs on the version pairs lineage proposes"),
    Edge("NEX-IMG", "NEX-ALN", CO, "Image features, for image pairs"),
    Edge("NEX-VID", "NEX-ALN", CO, "Frame features, for video pairs"),
    Edge("NEX-ALN", "NEX-TRN", CO, "Time mapping, for time-based pairs"),
    Edge("NEX-MOC", "NEX-TRN", R, "Transformations are analysed between proposed versions"),
    Edge("NEX-IMG", "NEX-CMC", OP, "Image findings to correlate"),
    Edge("NEX-VID", "NEX-CMC", OP, "Video findings to correlate"),
    Edge("NEX-AUD", "NEX-CMC", OP, "Audio findings to correlate"),
    Edge("NEX-PRV", "NEX-CMC", OP, "Provenance observations to correlate"),
    Edge("NEX-TRN", "NEX-CMC", OP, "Transformation hypotheses to correlate"),
    Edge("NEX-SRC", "NEX-EGC", OP, "Source nodes"),
    Edge("NEX-MOC", "NEX-EGC", OP, "Version-relationship edges"),
    Edge("NEX-TRN", "NEX-EGC", OP, "Transformation-hypothesis nodes and edges"),
    Edge("NEX-CMC", "NEX-EGC", OP, "Support and contradiction edges"),
    Edge("NEX-EGC", "NEX-REC", R, "Reconstruction orders the evidence graph"),
    Edge("NEX-REC", "NEX-INV", R, "Case-level conclusions review a reconstruction"),
    Edge("NEX-INV", "NEX-RPT", OP, "A DRAFT report needs no review; a FINAL report requires it (enforced by the Report Service)"),
)

BY_ID: dict[str, ModuleSpec] = {m.module_id: m for m in MODULES}
TMIR_COORDINATED: tuple[str, ...] = tuple(m.module_id for m in MODULES if m.owner is Owner.TMIR)


def spec(module_id: str) -> ModuleSpec:
    return BY_ID[module_id]


def upstream_edges(module_id: str) -> list[Edge]:
    return [e for e in EDGES if e.downstream == module_id]


def downstream_edges(module_id: str) -> list[Edge]:
    return [e for e in EDGES if e.upstream == module_id]


def solid_edges() -> list[tuple[str, str]]:
    return [(e.upstream, e.downstream) for e in EDGES]


def topological_order() -> list[str]:
    """Kahn's algorithm over the registry; raises ValueError if a cycle exists."""
    indegree = {m.module_id: 0 for m in MODULES}
    for e in EDGES:
        indegree[e.downstream] += 1
    ready = [m.module_id for m in MODULES if indegree[m.module_id] == 0]
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for e in downstream_edges(node):
            indegree[e.downstream] -= 1
            if indegree[e.downstream] == 0:
                ready.append(e.downstream)
    if len(order) != len(MODULES):
        raise ValueError(f"Module graph contains a cycle among: {sorted(set(BY_ID) - set(order))}")
    return order


def applies_to(module_id: str, facts: EvidenceFacts) -> bool:
    m = BY_ID[module_id]
    return m.applies(facts) if m.applies else True


# ── decisions ─────────────────────────────────────────────────────────────────────────────────

class Action(StrEnum):
    RUN = "RUN"
    WAIT = "WAIT"
    SKIP = "SKIP"


@dataclass
class Decision:
    action: Action
    reason: SkipReason | None = None
    using: list[str] = field(default_factory=list)       # upstreams whose results will be read
    waiting_on: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


_MISSING = object()


def decide(
    module_id: str,
    *,
    applicable: bool,
    upstream: Mapping[str, ExecutionState | None],
    upstream_applicable: Mapping[str, bool] | None = None,
) -> Decision:
    """Whether a module can run now for one scope.

    `upstream` maps each upstream module that is part of this run to its current state (None or a
    non-terminal state while it is still pending). An upstream absent from the map is not part of the run.
    Domain-service upstreams (CM, CAP, EVD) are passed as COMPLETED once their records exist.
    `upstream_applicable` says, for CONDITIONAL edges, whether the upstream applies to the same scope.
    """
    if not applicable:
        return Decision(Action.SKIP, SkipReason.NOT_APPLICABLE)
    upstream_applicable = upstream_applicable or {}
    d = Decision(Action.RUN)

    for e in upstream_edges(module_id):
        u = e.upstream
        st = upstream.get(u, _MISSING)
        if e.kind is EdgeKind.CONDITIONAL and upstream_applicable.get(u) is False:
            continue  # does not apply to this scope: not needed, not a limitation
        if st is _MISSING:
            if e.kind is EdgeKind.REQUIRED:
                return Decision(Action.SKIP, SkipReason.NO_INPUT, limitations=[f"{u} is required but is not part of this run"])
            d.limitations.append(f"{u} was not part of this run")
            continue
        if st is None or not st.terminal:
            d.waiting_on.append(u)
            continue
        if st.produced_output:
            d.using.append(u)
            if st is ExecutionState.PARTIALLY_COMPLETED:
                d.limitations.append(f"{u} completed only partially")
            continue
        # terminal without output
        if e.kind is EdgeKind.REQUIRED:
            no_input = st in (ExecutionState.SKIPPED, ExecutionState.UNAVAILABLE)
            return Decision(Action.SKIP, SkipReason.NO_INPUT if no_input else SkipReason.UPSTREAM_FAILED,
                            limitations=[f"{u} ended {st.value} without a result"])
        d.limitations.append(f"{u} ended {st.value}; its input is missing")

    m = BY_ID[module_id]
    if m.require_any:
        relevant = [u for u in m.require_any if not (upstream_applicable.get(u) is False)]
        if not any(u in d.using for u in relevant) and not any(u in d.waiting_on for u in relevant):
            failed = any(upstream.get(u) in (ExecutionState.FAILED, ExecutionState.CANCELLED) for u in relevant)
            return Decision(Action.SKIP, SkipReason.UPSTREAM_FAILED if failed else SkipReason.NO_INPUT,
                            limitations=d.limitations + [f"none of {', '.join(relevant)} produced output"])

    if d.waiting_on:
        d.action = Action.WAIT
    return d


# ── self-check ────────────────────────────────────────────────────────────────────────────────

def validate() -> None:
    ids = [m.module_id for m in MODULES]
    if len(ids) != 18 or len(set(ids)) != 18:
        raise ValueError("The registry must define exactly 18 distinct modules")
    if [m.number for m in MODULES] != list(range(1, 19)):
        raise ValueError("Module numbers must run 1..18 in order")
    pairs = solid_edges()
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate edge in the registry")
    for e in EDGES:
        if e.upstream not in BY_ID or e.downstream not in BY_ID:
            raise ValueError(f"Edge references an unknown module: {e}")
    for m in MODULES:
        ups = {e.upstream for e in upstream_edges(m.module_id)}
        if not set(m.require_any) <= ups:
            raise ValueError(f"{m.module_id}.require_any names modules that are not its upstreams")
        if m.owner is Owner.TMIR and m.scope not in (Scope.EVIDENCE, Scope.PAIR, Scope.CASE):
            raise ValueError(f"T-MIR module {m.module_id} needs an EVIDENCE, PAIR or CASE scope")
        if m.scope is Scope.EVIDENCE and m.applies is None:
            raise ValueError(f"Evidence-scoped module {m.module_id} needs an applicability rule")
    topological_order()


validate()
