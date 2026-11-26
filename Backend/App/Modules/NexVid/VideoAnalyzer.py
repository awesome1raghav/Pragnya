"""NEX-VID Video Forensics: timing structure and visual continuity of the preserved original (archive §4, module 06).

Methods (each reports what it measured):
  TIMING      packet presentation timestamps of the first video stream: interval regularity (variable frame
              rate), gaps far longer than the typical interval, non-increasing timestamps, keyframe spacing.
              Edits, re-encodes and screen recordings change these; so do some cameras and streaming.
  CONTINUITY  frames sampled at a fixed rate (grayscale, downscaled): the mean absolute change between
              consecutive samples, with abrupt changes as candidate discontinuities at exact timestamps.
              A scene cut in an edited video is normal; this flags where to look, not what happened.
  SIGNATURES  a 64-bit difference hash per sampled frame (features for NEX-FPM and NEX-ALN).
Sampled-frame times come from FFmpeg's own presentation timestamps, so the frame/time mapping is reproducible.
Audio is NEX-AUD's (it extracts the track itself). An evaluated video deepfake detector is not installed.
"""

import json
from pathlib import Path

import numpy as np

from Backend.App.Contracts.Artifacts import ArtifactKind
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind, TimeRange
from Backend.App.Modules.Engine import DETECTOR_NOT_INSTALLED, ArtifactOut, EngineOutput, png, r, robust_z
from Backend.App.Utils import MediaDecode

VERSION = "nextron-vid/1"
MODULE = "NEX-VID"
PARAMETERS = {"sample_fps": 4, "max_samples": 600, "sample_width": 160, "change_z": 6.0, "gap_factor": 2.5, "max_candidates": 20}


def _dhash(frame: np.ndarray) -> str:
    h, w = frame.shape
    ys = (np.arange(8) * h / 8).astype(int)
    xs = (np.arange(9) * w / 9).astype(int)
    small = frame[np.ix_(ys, xs)].astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def _contact_sheet(frames: np.ndarray, times: list[float], picks: list[int]) -> np.ndarray:
    tiles = [frames[i] for i in picks]
    h, w = tiles[0].shape
    cols = min(4, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.full((rows * (h + 4) + 4, cols * (w + 4) + 4), 24, dtype=np.uint8)
    for n, tile in enumerate(tiles):
        y, x = 4 + (n // cols) * (h + 4), 4 + (n % cols) * (w + 4)
        sheet[y:y + h, x:x + w] = tile
    return sheet


def analyze(path: Path, evidence_id, *, settings) -> EngineOutput:
    ffprobe = settings.FFPROBE_PATH
    ffmpeg = MediaDecode.ffmpeg_for(ffprobe)
    timeout = settings.MODULE_TIMEOUT_SECONDS
    out = EngineOutput(ExecutionState.PARTIALLY_COMPLETED, DETECTOR_NOT_INSTALLED,
                       "No face-manipulation detector has been benchmarked yet (GenD is shortlisted; it needs a licensed "
                       "face-swap test set), so no synthetic-video assessment was made; the timing and continuity measurements below ran.")
    out.tool_versions = {"ffprobe": MediaDecode.tool_version(ffprobe), "ffmpeg": MediaDecode.tool_version(ffmpeg), "numpy": np.__version__}
    ev = [evidence_id]

    def finding(kind, title, description, measurement, *, score=None, time_range=None, limitations=(), artifacts=()):
        out.findings.append(Finding(
            module_id=MODULE, evidence_ids=ev, assertion=Assertion.OBSERVATION, finding_type=kind, title=title, description=description,
            measurement=measurement, score=score, score_kind=ScoreKind.METHOD_SPECIFIC if score is not None else None, time_range=time_range,
            limitations=list(limitations), supporting_artifact_ids=[a.artifact_id for a in artifacts], parameters=PARAMETERS))

    # timing structure
    timing = MediaDecode.video_packets(path, ffprobe, timeout)
    if timing.truncated:
        out.limitations.append("Packet timing was read for the first 200,000 packets only")
    pts = np.sort(timing.pts)
    if pts.size >= 3:
        intervals = np.diff(pts)
        positive = intervals[intervals > 0]
        median = float(np.median(positive)) if positive.size else 0.0
        gaps = np.nonzero(intervals > PARAMETERS["gap_factor"] * median)[0] if median else np.array([], dtype=int)
        non_increasing = int((np.diff(timing.pts) <= 0).sum())
        cv = float(positive.std() / positive.mean()) if positive.size and positive.mean() else 0.0
        keys = np.sort(timing.pts[timing.keyframe])
        key_intervals = np.diff(keys)
        measurement = {"packets": int(pts.size), "median_interval_s": r(median, 6), "nominal_fps": r(1 / median, 3) if median else None,
                       "interval_cv": r(cv), "gaps": int(gaps.size), "non_increasing_pts_in_decode_order": non_increasing,
                       "keyframes": int(keys.size), "median_keyframe_interval_s": r(np.median(key_intervals), 3) if key_intervals.size else None,
                       "keyframe_interval_cv": r(key_intervals.std() / key_intervals.mean(), 4) if key_intervals.size > 1 and key_intervals.mean() else None}
        timing_limits = ["B-frames reorder decode timestamps legitimately; only presentation order is assessed for gaps",
                         "Variable frame rate is normal for phone cameras and screen recordings"]
        for i in gaps[: PARAMETERS["max_candidates"]]:
            finding("TIMESTAMP_GAP", f"Frame timing gap at {pts[i]:.3f} s",
                    f"No frame for {intervals[i]:.3f} s, {intervals[i] / median:.1f}× the typical interval.",
                    {"gap_s": r(intervals[i], 6), "typical_interval_s": r(median, 6)}, score=r(intervals[i] / median, 2),
                    time_range=TimeRange(start_seconds=r(pts[i], 6), end_seconds=r(pts[i + 1], 6)), limitations=timing_limits)
        finding("FRAME_TIMING", "Frame timing measured",
                ("Regular frame intervals." if cv < 0.05 else "Frame intervals vary (variable frame rate).") +
                (f" {gaps.size} gap(s) longer than {PARAMETERS['gap_factor']}× the typical interval." if gaps.size else ""),
                measurement, score=r(cv), limitations=timing_limits)
    else:
        out.limitations.append("Fewer than three video packets: timing was not assessed")

    # sampled frames
    sampled = MediaDecode.sample_frames(path, ffmpeg, timeout, fps=PARAMETERS["sample_fps"], max_frames=PARAMETERS["max_samples"],
                                        width=PARAMETERS["sample_width"])
    if len(sampled.frames) >= PARAMETERS["max_samples"]:
        out.limitations.append(f"Continuity was measured on the first {PARAMETERS['max_samples']} samples "
                               f"({PARAMETERS['max_samples'] / PARAMETERS['sample_fps']:.0f} s)")
    frames, times = sampled.frames, sampled.times
    if len(frames) >= 3:
        change = np.abs(np.diff(frames.astype(np.int16), axis=0)).mean(axis=(1, 2))
        z = robust_z(change)
        candidates = [int(i) for i in np.argsort(-z) if z[i] > PARAMETERS["change_z"] and change[i] > 4][: PARAMETERS["max_candidates"]]
        lim = ["Scene cuts, camera motion, flashes and fades also produce abrupt changes",
               f"Samples are {1 / PARAMETERS['sample_fps']:.2f} s apart; a change is located only to that precision"]
        for i in sorted(candidates):
            finding("VISUAL_DISCONTINUITY", f"Abrupt visual change at {times[i + 1]:.2f} s",
                    "Consecutive samples differ much more than the rest of the video does.",
                    {"mean_abs_change": r(change[i], 3), "median_change": r(np.median(change), 3)}, score=r(z[i], 2),
                    time_range=TimeRange(start_seconds=r(times[i], 4), end_seconds=r(times[i + 1], 4)), limitations=lim)
        picks = sorted({0, len(frames) - 1, *[min(i + 1, len(frames) - 1) for i in candidates[:6]],
                        *np.linspace(0, len(frames) - 1, 8).astype(int).tolist()})[:12]
        sheet = ArtifactOut(ArtifactKind.FRAME_SET, "image/png", "png", png(_contact_sheet(frames, times, picks)),
                            {"frame_times_s": [r(times[i], 4) for i in picks], "width": sampled.width, "height": sampled.height, "grayscale": True})
        signatures = ArtifactOut(ArtifactKind.FINGERPRINT, "application/json", "json",
                                 json.dumps({"algorithm": "dHash 64-bit per sampled frame", "sample_fps": PARAMETERS["sample_fps"],
                                             "frames": [{"t": r(t, 4), "dhash": _dhash(f)} for t, f in zip(times, frames)]},
                                            separators=(",", ":")).encode())
        out.artifacts += [sheet, signatures]
        finding("VISUAL_CONTINUITY", "Visual continuity measured",
                f"{len(frames)} samples over {times[-1] - times[0]:.2f} s; {len(candidates)} abrupt change(s) above the threshold.",
                {"samples": len(frames), "first_s": r(times[0], 4), "last_s": r(times[-1], 4), "candidates": len(candidates),
                 "median_change": r(np.median(change), 3), "max_robust_z": r(z.max(), 2)},
                score=r(z.max(), 2), limitations=lim, artifacts=[sheet, signatures])
    else:
        out.limitations.append("Fewer than three frames could be sampled: continuity was not assessed")
    out.limitations.append("No benchmarked video deepfake detector: synthetic or face-swapped content was not assessed")
    return out
