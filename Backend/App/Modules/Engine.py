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
