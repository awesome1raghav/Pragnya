"""What a media engine (NEX-IMG, NEX-VID, NEX-AUD, NEX-PRV) returns to T-MIR, plus small numeric helpers.

An engine reads the preserved original and returns an EngineOutput: its status, findings, derived artifacts
(bytes plus kind and MIME type; T-MIR stores them and records their SHA-256), tool versions and limitations.
Engines never touch the database. Scores are each method's own measurement (score_kind METHOD_SPECIFIC unless
stated otherwise); no engine produces a confidence, because none of these methods is calibrated.
"""

import io
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from Backend.App.Contracts.Artifacts import ArtifactKind
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Finding


@dataclass
class ArtifactOut:
    kind: ArtifactKind
    mime_type: str
    extension: str
    data: bytes
    attributes: dict[str, Any] = field(default_factory=dict)
    artifact_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class EngineOutput:
    status: ExecutionState
    reason: str | None = None
    detail: str | None = None
    findings: list[Finding] = field(default_factory=list)
    artifacts: list[ArtifactOut] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tool_versions: dict[str, str] = field(default_factory=dict)
    error: str | None = None


DETECTOR_NOT_INSTALLED = "DETECTOR_NOT_INSTALLED"


def png(array: np.ndarray) -> bytes:
    """uint8 grayscale (h, w) or RGB (h, w, 3) array as PNG bytes (deterministic: no timestamps in the file)."""
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(array)).save(buf, "PNG", optimize=False)
    return buf.getvalue()


def heatmap(values: np.ndarray, *, size: tuple[int, int] | None = None) -> np.ndarray:
    """Scale a 2-D array to 0-255 and colour it dark → amber → white (the UI's palette), optionally resized (w, h)."""
    v = values.astype(np.float64)
    lo, hi = np.percentile(v, 1), np.percentile(v, 99.5)
    t = np.clip((v - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros_like(v)
    rgb = np.stack([np.clip(t * 2, 0, 1) * 233 + np.clip(t * 2 - 1, 0, 1) * 22,
                    np.clip(t * 2, 0, 1) * 162 + np.clip(t * 2 - 1, 0, 1) * 93,
                    np.clip(t * 2 - 1, 0, 1) * 255], axis=-1)
    image = rgb.clip(0, 255).astype(np.uint8)
    if size:
        image = np.asarray(Image.fromarray(image).resize(size, Image.Resampling.NEAREST))
    return image


def robust_z(x: np.ndarray) -> np.ndarray:
    """(x - median) / (1.4826 · MAD); zeros when the spread is zero."""
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return x
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826
    return (x - med) / mad if mad > 1e-12 else np.zeros_like(x)


def r(value: float, digits: int = 4) -> float:
    return float(round(float(value), digits))


# ── pretrained detectors (run in the detector host process) ──────────────────────────────────

DETECTOR_FAILED = "DETECTOR_FAILED"
DETECTOR_DISABLED = "DETECTOR_DISABLED"


@dataclass
class DetectorRun:
    """What one detector call produced, for the engine to put in its result."""

    status: ExecutionState            # COMPLETED when the detector scored, otherwise PARTIALLY_COMPLETED
    reason: str | None
    detail: str | None
    score: float | None = None
    info: Any = None                  # Detectors.Host.DetectorInfo
    seconds: float | None = None


def run_detector(settings, name: str, path, *, what: str) -> DetectorRun:
    """Score `path` with the configured detector; any problem becomes a stated reason, never a guess."""
    from Backend.App.Detectors import Host

    if settings is None or not settings.DETECTORS_ENABLED or not name:
        return DetectorRun(ExecutionState.PARTIALLY_COMPLETED, DETECTOR_DISABLED, f"The {what} detector is turned off in this installation.")
    host = Host.shared_host()
    try:
        info = host.info(name)
        score, seconds = host.score(name, path, timeout=settings.DETECTOR_TIMEOUT_SECONDS)
    except Host.DetectorUnavailable as exc:
        return DetectorRun(ExecutionState.PARTIALLY_COMPLETED, DETECTOR_NOT_INSTALLED, f"The {what} detector {name} is not available: {exc}")
    except Host.DetectorFailed as exc:
        return DetectorRun(ExecutionState.PARTIALLY_COMPLETED, DETECTOR_FAILED, f"The {what} detector {name} did not produce a score: {exc}")
    return DetectorRun(ExecutionState.COMPLETED, None, None, score=score, info=info, seconds=seconds)


def detector_finding(module: str, evidence_id, run: DetectorRun, *, kind: str, subject: str, benchmark: str,
                     time_range=None, measurement: dict | None = None) -> Finding:
    """An INFERENCE with the model's own score. Wording states what the number is and is not."""
    from Backend.App.Contracts.Findings import Assertion, ScoreKind

    from Backend.App.Detectors.Benchmarks import operating

    op = operating(run.info.name)
    above = run.score >= op.threshold
    return Finding(
        module_id=module, evidence_ids=[evidence_id], assertion=Assertion.INFERENCE, finding_type=kind,
        title=(f"{run.info.name} scores this {subject} {run.score:.4g}: "
               + ("above" if above else "below") + " its operating threshold"
               + (" (resembles the synthetic material it was trained on)" if above else "")),
        description=(f"{run.info.name} returns a score between 0 and 1. It is compared with {op.threshold:g}, "
                     f"{op.source}. The score is the model's own output, not a probability that this file is synthetic."),
        measurement={"detector": run.info.name, "detector_version": run.info.version, "licence": run.info.licence,
                     "score": r(run.score, 8), "threshold": op.threshold, "threshold_source": op.source,
                     "above_threshold": above, "seconds": run.seconds} | (measurement or {}),
        score=r(run.score, 8), score_kind=ScoreKind.METHOD_SPECIFIC, time_range=time_range,
        limitations=[f"Trained on: {run.info.trained_on}", f"Measured locally: {benchmark}",
                     "Generators and voice-cloning tools released after the model was trained may not be recognised",
                     "Recompression, resizing, screenshots and re-recording change the score"],
    )
