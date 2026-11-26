"""NEX-IMG Image Forensics: measurement methods over the preserved original (archive §4, module 05).

Methods (each reports what it measured; none decides "manipulated" or "authentic"):
  ELA        error level analysis: difference after one JPEG re-save at a fixed quality. A limited heuristic:
             re-encoding, resizing and texture change it; it is never a deepfake detector.
  NOISE      local noise level of the high-pass residual per block; regions whose noise differs strongly
             from the rest can come from splicing, retouching or simply from different content.
  RESAMPLING periodic interpolation traces: the mean absolute second derivative along rows and along columns,
             whose spectrum has a sharp peak when the image was resized by a non-integer factor (Gallagher 2005;
             Mahdian & Saic 2008). Integer factors (exactly 2x) and strong recompression hide the trace.
  JPEG_QT    for JPEG files, the luminance quantisation table and the IJG quality it best matches.
  HASHES     average, difference and DCT perceptual hashes (features for NEX-FPM; not evidence by themselves).
DETECTOR   the configured pretrained synthetic-image detector (Detectors/Host.py, benchmarked locally), reported as an
             INFERENCE with the model's own score. Without it the result is PARTIALLY_COMPLETED and says why.
"""

import io
from pathlib import Path

import numpy as np
import PIL
from PIL import Image, ImageOps

from Backend.App.Contracts.Artifacts import ArtifactKind
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion, Finding, Region, ScoreKind
from Backend.App.Detectors import Benchmarks
from Backend.App.Modules.Engine import ArtifactOut, EngineOutput, detector_finding, heatmap, png, r, robust_z, run_detector

VERSION = "nextron-img/1"
MODULE = "NEX-IMG"
PARAMETERS = {"ela_quality": 90, "ela_grid": 16, "noise_block": 32, "z_threshold": 4.0, "resampling_z": 20.0, "max_side": 4096}
MAX_PIXELS = 80_000_000  # refuse decompression bombs before decoding


def _load(path: Path) -> tuple[Image.Image, Image.Image, list[str]]:
    notes: list[str] = []
    with Image.open(path) as probe:
        if probe.width * probe.height > MAX_PIXELS:
            raise ValueError(f"image has {probe.width * probe.height} pixels; the limit is {MAX_PIXELS}")
    original = Image.open(path)
    original.load()
    if getattr(original, "n_frames", 1) > 1:
        notes.append("Animated image: only the first frame was analysed")
    rgb = ImageOps.exif_transpose(original).convert("RGB")  # analyse in display orientation, so regions match what is shown
    if max(rgb.size) > PARAMETERS["max_side"]:
        scale = PARAMETERS["max_side"] / max(rgb.size)
        rgb = rgb.resize((max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale))), Image.Resampling.LANCZOS)
        notes.append(f"Analysed a downscaled copy (longest side {PARAMETERS['max_side']} px); fine detail measurements are weaker")
    return original, rgb, notes


def _cells(values: np.ndarray, cell: int) -> np.ndarray:
    h, w = values.shape[:2]
    gh, gw = max(1, h // cell), max(1, w // cell)
    v = values[: gh * cell, : gw * cell]
    return v.reshape(gh, cell, gw, cell).mean(axis=(1, 3))


def _grid(values: np.ndarray, n: int) -> tuple[np.ndarray, int, int]:
    h, w = values.shape
    ch, cw = max(1, h // n), max(1, w // n)
    v = values[: ch * n, : cw * n]
    return v.reshape(n, ch, n, cw).mean(axis=(1, 3)), ch, cw


def _region(mask: np.ndarray, cell_h: float, cell_w: float, h: int, w: int) -> Region | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    x0, x1 = xs.min() * cell_w, (xs.max() + 1) * cell_w
    y0, y1 = ys.min() * cell_h, (ys.max() + 1) * cell_h
    return Region(x=r(100 * x0 / w, 2), y=r(100 * y0 / h, 2), w=r(max(0.01, 100 * (min(x1, w) - x0) / w), 2),
                  h=r(max(0.01, 100 * (min(y1, h) - y0) / h), 2))


def _ela(rgb: Image.Image) -> tuple[np.ndarray, dict]:
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=PARAMETERS["ela_quality"])
    resaved = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    diff = np.abs(np.asarray(rgb, dtype=np.int16) - np.asarray(resaved, dtype=np.int16)).max(axis=2).astype(np.float64)
    return diff, {"mean": r(diff.mean()), "p99": r(np.percentile(diff, 99))}


def _box3(a: np.ndarray) -> np.ndarray:
    p = np.pad(a, 1, mode="edge")
    return sum(p[dy:dy + a.shape[0], dx:dx + a.shape[1]] for dy in range(3) for dx in range(3)) / 9.0


def _perceptual(gray: Image.Image) -> dict:
    def bits(b: np.ndarray) -> str:
        return f"{int(''.join('1' if x else '0' for x in b.flatten()), 2):016x}"

    a8 = np.asarray(gray.resize((8, 8), Image.Resampling.LANCZOS), dtype=np.float64)
    d9 = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.float64)
    p32 = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    n = 32
    k = np.arange(n)
    dct = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
    coeffs = (dct @ p32 @ dct.T)[:8, :8]
    low = coeffs.flatten()[1:]
    return {"ahash": bits(a8 > a8.mean()), "dhash": bits(d9[:, 1:] > d9[:, :-1]),
            "phash": bits(coeffs > np.median(low)), "algorithm": "8x8 aHash, 9x8 dHash, 32x32 DCT pHash (64-bit hex)"}


_IJG_LUMA = np.array([16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
                      14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
                      49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99], dtype=np.float64)


def _ijg_table(q: int) -> np.ndarray:
    scale = 5000 / q if q < 50 else 200 - 2 * q
    return np.clip(np.floor((_IJG_LUMA * scale + 50) / 100), 1, 255)


def analyze(path: Path, evidence_id, *, settings=None) -> EngineOutput:
    out = EngineOutput(ExecutionState.PARTIALLY_COMPLETED)  # the detector step below decides the final status
    out.tool_versions = {"pillow": PIL.__version__, "numpy": np.__version__}
    original, rgb, notes = _load(path)
    out.limitations += notes
    w, h = rgb.size
    ev = [evidence_id]
    gray = rgb.convert("L")

    def finding(kind: str, title: str, description: str, measurement: dict, *, score=None, region=None, limitations=(),
                artifacts=(), assertion=Assertion.OBSERVATION) -> None:
        out.findings.append(Finding(
            module_id=MODULE, evidence_ids=ev, assertion=assertion, finding_type=kind, title=title, description=description,
            measurement=measurement, score=score, score_kind=ScoreKind.METHOD_SPECIFIC if score is not None else None,
            region=region, limitations=list(limitations), supporting_artifact_ids=[a.artifact_id for a in artifacts],
            parameters=PARAMETERS,
        ))

    # ELA
    diff, ela_stats = _ela(rgb)
    grid, ch, cw = _grid(diff, PARAMETERS["ela_grid"])
    z = robust_z(grid)
    flagged = (z > PARAMETERS["z_threshold"]) & (grid > 2 * np.median(grid) + 1)
    ela_png = ArtifactOut(ArtifactKind.HEATMAP, "image/png", "png", png(heatmap(diff)), {"method": "ELA", "quality": PARAMETERS["ela_quality"], "width": w, "height": h})
    out.artifacts.append(ela_png)
    ela_limits = ["ELA is a limited heuristic: re-encoding, resizing, sharpening and texture all change it",
                  "It cannot tell a manipulated region from one that simply has more detail"]
    if flagged.any() and flagged.mean() < 0.5:
        finding("ELA_LOCAL_RESPONSE", "Localised error-level response",
                f"{int(flagged.sum())} of {flagged.size} grid cells re-compress very differently from the rest of the image.",
                ela_stats | {"flagged_cells": int(flagged.sum()), "grid": PARAMETERS["ela_grid"], "max_cell_robust_z": r(z.max(), 2)},
                score=r(z.max(), 2), region=_region(flagged, ch, cw, h, w), limitations=ela_limits, artifacts=[ela_png])
    else:
        finding("ELA_UNIFORM_RESPONSE", "No localised error-level response",
                "Re-compression error is spread evenly across the image at this grid size.",
                ela_stats | {"max_cell_robust_z": r(z.max(), 2) if z.size else 0.0}, score=r(z.max(), 2) if z.size else 0.0,
                limitations=ela_limits, artifacts=[ela_png])

    # noise residual consistency
    g = np.asarray(gray, dtype=np.float64)
    residual = g - _box3(g)
    block = PARAMETERS["noise_block"]
    if min(g.shape) >= 2 * block:
        std = np.sqrt(np.maximum(_cells(residual ** 2, block), 1e-9))
        nz = robust_z(np.log(std))
        noisy = np.abs(nz) > PARAMETERS["z_threshold"]
        noise_png = ArtifactOut(ArtifactKind.HEATMAP, "image/png", "png", png(heatmap(np.log(std), size=(w, h))), {"method": "NOISE", "block": block})
        out.artifacts.append(noise_png)
        lim = ["Flat or blurred areas (sky, walls, bokeh) legitimately have less noise than textured ones"]
        if noisy.any() and noisy.mean() < 0.3:
            finding("NOISE_LEVEL_INCONSISTENCY", "Region with a different noise level",
                    f"{int(noisy.sum())} of {noisy.size} blocks have a residual noise level far from the image's typical level.",
                    {"blocks": int(noisy.size), "outlier_blocks": int(noisy.sum()), "median_noise_std": r(np.median(std)), "max_abs_robust_z": r(np.abs(nz).max(), 2)},
                    score=r(np.abs(nz).max(), 2), region=_region(noisy, block, block, h, w), limitations=lim, artifacts=[noise_png])
        else:
            finding("NOISE_LEVEL_CONSISTENT", "Noise level consistent across blocks", "No block's residual noise differs strongly from the rest.",
                    {"blocks": int(noisy.size), "median_noise_std": r(np.median(std)), "max_abs_robust_z": r(np.abs(nz).max(), 2)},
                    score=r(np.abs(nz).max(), 2), limitations=lim, artifacts=[noise_png])
    else:
        out.limitations.append(f"Image smaller than {2 * block} px: noise consistency was not measured")

    # resampling traces (second-derivative periodicity, per axis)
    if min(g.shape) >= 64:
        axes = {}
        for name, a in (("horizontal", g), ("vertical", g.T)):
            d2 = np.abs(a[:, 2:] - 2 * a[:, 1:-1] + a[:, :-2]).mean(axis=0)
            d2 = d2 - np.convolve(d2, np.ones(15) / 15, mode="same")
            spectrum = np.abs(np.fft.rfft(d2 * np.hanning(d2.size)))
            freqs = np.fft.rfftfreq(d2.size)
            band = freqs > 0.05
            z = robust_z(spectrum[band])
            i = int(np.argmax(z))
            axes[name] = {"peak_robust_z": r(z[i], 2), "peak_frequency_cycles_per_px": r(freqs[band][i], 4)}
        strongest = max(v["peak_robust_z"] for v in axes.values())
        found = strongest > PARAMETERS["resampling_z"]
        lim = ["Exact integer factors (such as 2x) and strong recompression can hide the trace",
               "Periodic textures (fabric, grilles, screens) can produce a similar peak"]
        finding("RESAMPLING_TRACES" if found else "NO_RESAMPLING_TRACES",
                "Periodic interpolation traces (resized image)" if found else "No periodic interpolation traces",
                "The second derivative is periodic, as interpolation by a non-integer factor makes it." if found else
                "No sharp periodicity in the second derivative along either axis.",
                axes, score=strongest, limitations=lim)
    else:
        out.limitations.append("Image smaller than 64 px: resampling traces were not measured")

    # JPEG quantisation
    tables = getattr(original, "quantization", None)
    if original.format == "JPEG" and tables:
        luma = np.asarray(tables[0], dtype=np.float64)  # Pillow returns tables in natural (row-major) order
        errors = {q: float(np.abs(_ijg_table(q) - luma).mean()) for q in range(1, 101)}
        best = min(errors, key=errors.get)
        standard = errors[best] < 0.5
        finding("JPEG_QUANTIZATION", f"JPEG quantisation consistent with IJG quality {best}" if standard else "Non-standard JPEG quantisation table",
                "The luminance table matches the IJG reference table scaled to this quality." if standard else
                "The luminance table does not match a scaled IJG table: typical of camera firmware or specific software.",
                {"estimated_ijg_quality": best, "mean_abs_table_error": r(errors[best], 3), "matches_ijg_scaling": standard,
                 "tables": len(tables), "luma_table": [int(v) for v in luma]},
                limitations=["The table shows the last encoder only; earlier compressions are not visible here"])
    out.findings.append(Finding(module_id=MODULE, evidence_ids=ev, assertion=Assertion.OBSERVATION, finding_type="PERCEPTUAL_HASHES",
                                title="Perceptual hashes computed", description="Features for similarity search (NEX-FPM); not evidence on their own.",
                                measurement=_perceptual(gray), parameters=PARAMETERS))
    run = run_detector(settings, getattr(settings, "IMAGE_DETECTOR", ""), path, what="synthetic-image")
    if run.score is not None:
        out.status = ExecutionState.COMPLETED
        out.findings.append(detector_finding(MODULE, evidence_id, run, kind="SYNTHETIC_IMAGE_DETECTOR", subject="image",
                                             benchmark=Benchmarks.summary(run.info.name)))
        out.tool_versions[run.info.name] = run.info.version
    else:
        out.reason, out.detail = run.reason, run.detail + " The measurement methods below ran."
        out.limitations.append(run.detail)
    return out
