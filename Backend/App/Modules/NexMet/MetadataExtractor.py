"""NEX-MET metadata extraction: Pillow for images, FFprobe for video and audio.

Absent fields stay null. Embedded timestamps are reported separately from NEXTRON's own
receipt and preservation times and are never treated as when the content was made.
"""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import PIL
from PIL import Image

from Backend.App.Modules.NexMet import ExifAnalyzer
from Backend.App.Utils.MediaProbe import ProbeFailed, ProbeUnavailable, run_ffprobe

EXTRACTOR_REVISION = "nextron-met/1"


@dataclass
class ExtractionResult:
    status: str  # EXTRACTED | UNAVAILABLE | FAILED
    extractor: str
    extractor_version: str
    summary: dict[str, Any]
    raw: dict[str, Any] | None
    error: str | None = None


def _ratio(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        fraction = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return round(float(fraction), 6) if fraction else None


def _number(value: Any, kind=float):
    try:
        return kind(value) if value not in (None, "N/A", "") else None
    except (TypeError, ValueError):
        return None


def _rotation(stream: dict) -> int | None:
    for side_data in stream.get("side_data_list", []) or []:
        if "rotation" in side_data:
            return _number(side_data["rotation"], int)
    return _number((stream.get("tags") or {}).get("rotate"), int)


def summarize_ffprobe(probe: dict) -> dict[str, Any]:
    fmt = probe.get("format", {})
    video, audio, other = [], [], []
    for s in probe.get("streams", []):
        common = {"index": s.get("index"), "codec": s.get("codec_name"), "codec_long_name": s.get("codec_long_name"),
                  "duration_seconds": _number(s.get("duration")), "bit_rate": _number(s.get("bit_rate"), int)}
        if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic"):
            video.append(common | {
                "width": s.get("width"), "height": s.get("height"), "pixel_format": s.get("pix_fmt"),
                "average_frame_rate": _ratio(s.get("avg_frame_rate")), "nominal_frame_rate": _ratio(s.get("r_frame_rate")),
                "frame_count": _number(s.get("nb_frames"), int), "time_base": s.get("time_base"), "rotation_degrees": _rotation(s),
                "variable_frame_rate_suspected": _ratio(s.get("avg_frame_rate")) != _ratio(s.get("r_frame_rate")),
            })
        elif s.get("codec_type") == "audio":
            audio.append(common | {
                "sample_rate_hz": _number(s.get("sample_rate"), int), "channels": s.get("channels"),
                "channel_layout": s.get("channel_layout"), "sample_format": s.get("sample_fmt"),
            })
        else:
            other.append({"index": s.get("index"), "codec_type": s.get("codec_type"), "codec": s.get("codec_name")})

    embedded = {}
    if (fmt.get("tags") or {}).get("creation_time"):
        embedded["container_creation_time"] = fmt["tags"]["creation_time"]
    for s in probe.get("streams", []):
        if (s.get("tags") or {}).get("creation_time"):
            embedded[f"stream_{s.get('index')}_creation_time"] = s["tags"]["creation_time"]

    return {
        "container": {
            "format_name": fmt.get("format_name"),
            "format_long_name": fmt.get("format_long_name"),
            "duration_seconds": _number(fmt.get("duration")),
            "bit_rate": _number(fmt.get("bit_rate"), int),
            "stream_count": fmt.get("nb_streams"),
            "encoder": (fmt.get("tags") or {}).get("encoder"),
            "major_brand": (fmt.get("tags") or {}).get("major_brand"),
        },
        "video_streams": video,
        "audio_streams": audio,
        "other_streams": other,
        "has_audio": bool(audio),
        "has_video": bool(video),
        "embedded_timestamps": embedded,
        "embedded_timestamps_note": "Taken from the file; may be absent, wrong or edited.",
    }


def _extract_image(path: Path) -> ExtractionResult:
    version = f"Pillow {PIL.__version__}; {EXTRACTOR_REVISION}"
    try:
        with Image.open(path) as image:
            exif = ExifAnalyzer.analyze(image)
            summary = {
                "format": image.format,
                "mode": image.mode,
                "width": image.width,
                "height": image.height,
                "frame_count": getattr(image, "n_frames", 1),
                "animated": bool(getattr(image, "is_animated", False)),
                "has_icc_profile": "icc_profile" in image.info,
                "dpi": ExifAnalyzer.json_safe(image.info.get("dpi")),
                "exif_present": exif["present"],
                "exif": exif["tags"],
                "gps": exif["gps"],
                "embedded_timestamps": exif["embedded_timestamps"],
                "embedded_timestamps_note": "Taken from the file; may be absent, wrong or edited.",
            }
    except (OSError, ValueError, SyntaxError) as exc:
        return ExtractionResult("FAILED", "pillow", version, {}, None, f"{type(exc).__name__}: {exc}"[:500])
    return ExtractionResult("EXTRACTED", "pillow", version, summary, None)


def _extract_av(path: Path, ffprobe: str, timeout: float) -> ExtractionResult:
    try:
        probe, ffprobe_version = run_ffprobe(path, ffprobe, timeout)
    except ProbeUnavailable as exc:
        return ExtractionResult("UNAVAILABLE", "ffprobe", "not installed", {}, None, str(exc)[:500])
    except ProbeFailed as exc:
        return ExtractionResult("FAILED", "ffprobe", "unknown", {}, None, str(exc)[:500])
    return ExtractionResult("EXTRACTED", "ffprobe", f"{ffprobe_version}; {EXTRACTOR_REVISION}", summarize_ffprobe(probe), probe)


def extract(path: Path, media_type: str, *, ffprobe: str, timeout_seconds: float) -> ExtractionResult:
    if media_type == "IMAGE":
        return _extract_image(path)
    return _extract_av(path, ffprobe, timeout_seconds)
