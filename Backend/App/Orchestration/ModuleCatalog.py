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
