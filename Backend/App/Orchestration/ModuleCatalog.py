"""What each module can do in this build, layered over the dependency registry for GET /system/modules.

Identity, groups, ownership and edges come from TMir.DependencyRegistry (the one source of connectivity);
this file adds only the honest implementation status of each module, which must be updated as modules land.
"""

from dataclasses import dataclass
from typing import Literal

from Backend.App.Orchestration.TMir import DependencyRegistry as Registry

Status = Literal["IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"]

GROUPS = Registry.GROUPS
EDGES = tuple(Registry.solid_edges())
TMIR_COORDINATED = Registry.TMIR_COORDINATED
# T-MIR plans, runs, retries and records every coordinated module; per-pair expansion of ALN/TRN waits for MOC (Step 6).
TMIR_STATUS: Status = "PARTIAL"

_STATUS: dict[str, tuple[Status, tuple[str, ...], tuple[str, ...], str | None]] = {
    "NEX-CM": ("IMPLEMENTED",
               ("Create, list, filter, update cases", "Archive and reopen with history", "Statistics, summary, event history"),
               ("/cases", "/cases/{case_id}", "/cases/{case_id}/archive", "/cases/{case_id}/reopen", "/cases/{case_id}/events"), None),
    "NEX-CAP": ("IMPLEMENTED",
                ("Streamed multipart upload with size limit", "Signature and decode validation of images, video, audio"),
                ("/cases/{case_id}/evidence",), "URL, share and screen-capture acquisition are not built yet."),
    "NEX-EVD": ("IMPLEMENTED",
                ("Server-side SHA-256", "Read-only originals, re-verified before commit", "Chain-of-custody events", "Integrity verification"),
                ("/evidence/{evidence_id}/integrity", "/evidence/{evidence_id}/verify-integrity", "/evidence/{evidence_id}/history"), None),
    "NEX-MET": ("PARTIAL",
                ("Container and stream metadata (FFprobe)", "Image metadata and EXIF (Pillow)", "Runs in T-MIR workers with a result envelope"),
                ("/evidence/{evidence_id}/metadata", "/evidence/{evidence_id}/analysis"),
                "No XMP, device or inconsistency analysis yet."),
    "NEX-IMG": ("PARTIAL",
                ("Error level analysis with heatmap", "Block noise-level consistency with heatmap", "Residual spectrum periodicity",
                 "JPEG quantisation table and IJG quality", "Perceptual hashes (aHash, dHash, pHash)"),
                ("/evidence/{evidence_id}/analysis", "/artifacts/{artifact_id}"),
                "No evaluated synthetic-image detector is installed; results say so and no AI-generation verdict is made."),
    "NEX-VID": ("PARTIAL",
                ("Packet timing: gaps, variable frame rate, keyframe spacing", "Abrupt visual changes over timestamped samples",
                 "Per-frame difference hashes", "Contact sheet of sampled frames"),
                ("/evidence/{evidence_id}/analysis", "/artifacts/{artifact_id}"),
                "No evaluated video deepfake detector is installed; results say so."),
    "NEX-AUD": ("PARTIAL",
                ("Levels, clipping, DC offset", "Digital silence inside the recording", "Effective bandwidth",
                 "Abrupt spectral changes with times", "Spectrogram and a 16 kHz working copy", "Chromaprint when fpcalc is installed"),
                ("/evidence/{evidence_id}/analysis", "/artifacts/{artifact_id}"),
                "No evaluated synthetic-speech detector is installed; fpcalc is optional and reported when absent."),
    "NEX-SRC": ("PARTIAL",
                ("Add a source URL to a case; retrieval as a background job", "SSRF-safe fetching (public addresses only, pinned, every redirect checked)",
                 "Direct media and Open Graph / Twitter card media", "Claimed publication time and title", "Every attempt recorded with hops and addresses"),
                ("/cases/{case_id}/sources", "/sources/{source_id}", "/sources/{source_id}/history", "/sources/connectors"),
                "Only the generic connector exists: platform posts (YouTube, X, Instagram, Facebook, TikTok) need approved API connectors."),
    "NEX-FPM": ("IMPLEMENTED",
                ("Canonical pHash/dHash for images and one video frame per second", "Philips-style audio sub-fingerprints",
                 "Candidate search across the investigation, image to frame included"),
                ("/cases/{case_id}/modules/NEX-FPM/results",),
                "Thresholds set on a controlled set (precision 1.00, recall 0.91); 10 % crops are matched 71 % of the time."),
    "NEX-MOC": ("PARTIAL",
                ("Candidate relationships between versions", "Ordering by the sources' claimed publication times"),
                ("/cases/{case_id}/lineage",),
                "Relationships stay CANDIDATE; an investigator's decision on one is a separate review (NEX-INV) and never changes it."),
    "NEX-ALN": ("PARTIAL", ("Video offset and speed from frame matches", "Audio offset from sub-fingerprints", "Image scale"),
                ("/cases/{case_id}/modules",), "One frame per second (±0.5 s); one execution covers all of a case's pairs."),
    "NEX-TRN": ("PARTIAL", ("Trim, speed change, audio replacement, resize, crop/reframe, re-encode hypotheses",),
                ("/cases/{case_id}/modules",), "Hypotheses only; direction of an edit is not established."),
    "NEX-CMC": ("PARTIAL", ("Coincident audio-visual discontinuities", "Agreement and disagreement between provenance, image and detector signals"),
                ("/cases/{case_id}/modules",), "Rule-based correlation of stored findings; no learned fusion and no verdict."),
    "NEX-EGC": ("IMPLEMENTED", ("Case graph from stored records: evidence, sources, candidate versions, findings, correlations",
                 "Every edge names its supporting record", "Append-only snapshots; Neo4j projection"), ("/cases/{case_id}/graph",), None),
    "NEX-REC": ("PARTIAL", ("Timeline of claimed and measured times", "Conflicts between claimed creation and publication times"),
                ("/cases/{case_id}/reconstruction",), "No event-level reconstruction beyond dated statements and their conflicts."),
    "NEX-INV": ("IMPLEMENTED", ("Accept, reject, inconclusive or more evidence, with rationale", "Versioned, separate from findings",
                 "Case conclusion only after a reconstruction"), ("/cases/{case_id}/reviews",), "Single local operator: no reviewer roles yet."),
    "NEX-RPT": ("IMPLEMENTED", ("Versioned JSON and PDF reports with SHA-256", "DRAFT any time; FINAL needs a reviewed case conclusion"),
                ("/cases/{case_id}/reports", "/reports/{report_id}/download"), None),
    "NEX-PRV": ("IMPLEMENTED",
                ("C2PA manifests via the C2PA SDK", "Absent / valid / invalid / unsupported kept distinct",
                 "Signer, actions, ingredients and validation codes"),
                ("/evidence/{evidence_id}/analysis",),
                "No trust list is configured, so valid signers are reported as not vouched for. Remote manifests are not fetched."),
}


@dataclass(frozen=True)
class ModuleStatus:
    module_id: str
    number: int
    name: str
    group: str
    executed_by: str
    status: Status
    capabilities: tuple[str, ...]
    endpoints: tuple[str, ...]
    note: str | None


MODULES: tuple[ModuleStatus, ...] = tuple(
    ModuleStatus(
        m.module_id, m.number, m.name, m.group, m.owner.value,
        *_STATUS.get(m.module_id, ("NOT_IMPLEMENTED", (), (), None)),
    )
    for m in Registry.MODULES
)


def upstream(module_id: str) -> list[str]:
    return [e.upstream for e in Registry.upstream_edges(module_id)]


def downstream(module_id: str) -> list[str]:
    return [e.downstream for e in Registry.downstream_edges(module_id)]


topological_order = Registry.topological_order
