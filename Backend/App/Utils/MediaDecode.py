"""FFmpeg/FFprobe adapters for the media engines: sampled video frames with their timestamps, packet timing,
and decoded audio. Every call is bounded (frame count, size, duration, timeout), so a long or hostile file can
neither exhaust memory nor hang a worker; output is read from FFmpeg's stdout, never from a temporary file.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from Backend.App.Utils.MediaProbe import ProbeFailed, ProbeUnavailable, resolve_executable

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_PTS = re.compile(r"pts_time:\s*([0-9.]+)")


def ffmpeg_for(ffprobe: str) -> str:
    """FFmpeg next to the configured FFprobe (same install), else 'ffmpeg' on PATH."""
    candidate = Path(ffprobe)
    if candidate.is_file():
        sibling = candidate.with_name(candidate.name.replace("ffprobe", "ffmpeg"))
        if sibling.is_file():
            return str(sibling)
    return "ffmpeg"


@lru_cache(maxsize=8)
def tool_version(executable: str) -> str:
    try:
        result = subprocess.run([executable, "-hide_banner", "-version"], capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    first = (result.stdout or "").splitlines()[:1]
    return first[0].strip()[:120] if first else "unknown"


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    executable = resolve_executable(args[0])
    if executable is None:
        raise ProbeUnavailable(f"{args[0]} was not found")
    try:
        result = subprocess.run([executable, *args[1:]], capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ProbeFailed(f"{Path(args[0]).name} timed out after {timeout:g}s") from exc
    except OSError as exc:
        raise ProbeUnavailable(f"{args[0]} could not be started: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise ProbeFailed(result.stderr.decode("utf-8", "replace").strip()[-400:] or f"exit code {result.returncode}")
    return result


def streams(path: Path, ffprobe: str, timeout: float) -> list[dict]:
    out = _run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)], timeout)
    data = json.loads(out.stdout or b"{}")
    return data.get("streams", [])


@dataclass
class PacketTiming:
    pts: np.ndarray          # presentation times (s), in decode order as FFprobe lists them
    keyframe: np.ndarray     # bool per packet
    truncated: bool


def video_packets(path: Path, ffprobe: str, timeout: float, *, limit: int = 200_000) -> PacketTiming:
    out = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time,flags",
                "-of", "csv=p=0", str(path)], timeout)
    pts, key = [], []
    for line in out.stdout.decode("ascii", "replace").splitlines():
        parts = line.strip().split(",")
        if len(parts) < 2 or parts[0] in ("", "N/A"):
            continue
        try:
            pts.append(float(parts[0]))
        except ValueError:
            continue
        key.append("K" in parts[1])
        if len(pts) >= limit:
            break
    return PacketTiming(np.asarray(pts, dtype=np.float64), np.asarray(key, dtype=bool), len(pts) >= limit)


@dataclass
class SampledFrames:
    times: list[float]          # presentation time of each sampled frame (s), from FFmpeg's showinfo
    frames: np.ndarray          # (n, h, w) uint8 grayscale
    width: int
    height: int


def sample_frames(path: Path, ffmpeg: str, timeout: float, *, fps: float, max_frames: int, width: int) -> SampledFrames:
    """Grayscale frames at `fps` (at most `max_frames`), scaled to `width` (height keeps the aspect ratio, even)."""
    vf = f"fps={fps:g},scale={width}:-2:flags=area,format=gray,showinfo"
    out = _run([ffmpeg, "-v", "info", "-nostdin", "-i", str(path), "-map", "0:v:0", "-vf", vf, "-frames:v", str(max_frames),
                "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"], timeout)
    log = out.stderr.decode("utf-8", "replace")
    times = [float(t) for t in _PTS.findall(log)]
    size = re.findall(r"Stream #\d+:\d+.*?Video: rawvideo.*?, (\d+)x(\d+)", log)
    if not size:
        raise ProbeFailed("could not read the sampled frame size")
    w, h = int(size[-1][0]), int(size[-1][1])
    raw = np.frombuffer(out.stdout, dtype=np.uint8)
    n = raw.size // (w * h)
    frames = raw[: n * w * h].reshape(n, h, w)
    return SampledFrames(times[:n], frames, w, h)


def decode_audio(path: Path, ffmpeg: str, timeout: float, *, sample_rate: int, max_seconds: float) -> np.ndarray:
    """Mono float32 samples in [-1, 1] of the first audio stream, resampled to `sample_rate`, at most `max_seconds`."""
    out = _run([ffmpeg, "-v", "error", "-nostdin", "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(sample_rate),
                "-t", f"{max_seconds:g}", "-f", "f32le", "pipe:1"], timeout)
    return np.frombuffer(out.stdout, dtype="<f4").astype(np.float32, copy=False)
