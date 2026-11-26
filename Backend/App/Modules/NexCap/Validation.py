"""NEX-CAP media validation: what the staged bytes actually are, ignoring client claims.

1. A file signature (magic bytes) must match a supported image, video or audio family.
   This gate matters: FFprobe will happily "read" arbitrary text as a tty stream.
2. Images must fully decode with Pillow (with decompression-bomb protection).
   Video and audio must parse with FFprobe and contain a usable stream of the right kind.
The client's filename extension and Content-Type are recorded but never trusted.
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Utils.MediaProbe import ProbeFailed, ProbeUnavailable, run_ffprobe

# Pillow raises DecompressionBombError above twice this many pixels (about 179 megapixels).
Image.MAX_IMAGE_PIXELS = 89_478_485

IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp", "BMP": "image/bmp", "TIFF": "image/tiff"}


@dataclass(frozen=True)
class MediaIdentification:
    media_type: str  # IMAGE | VIDEO | AUDIO
    detected_format: str
    mime_type: str


def sniff_signature(head: bytes) -> tuple[str, str] | None:
    """Return (family, hint) from the first bytes, or None if unsupported."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "JPEG"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "PNG"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image", "GIF"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image", "WEBP"
    if head[:2] == b"BM":
        return "image", "BMP"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image", "TIFF"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "av", "wav"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "av", "avi"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"avif"):
            return None  # HEIF/AVIF stills: not supported yet
        if brand == b"qt  ":
            return "av", "mov"
        if brand in (b"M4A ", b"M4B "):
            return "av", "m4a"
        return "av", "mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "av", "matroska"
    if head.startswith(b"OggS"):
        return "av", "ogg"
    if head.startswith(b"fLaC"):
        return "av", "flac"
    if head.startswith(b"ID3"):
        return "av", "mp3"
    if len(head) >= 2 and head[0] == 0xFF:
        if head[1] & 0xF6 == 0xF0:
            return "av", "aac"
        if head[1] & 0xE0 == 0xE0:
            return "av", "mp3"
    return None


# FFprobe format_name values accepted for each signature hint.
_AV_FORMATS = {
    "wav": {"wav"},
    "avi": {"avi"},
    "mov": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    "mp4": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    "m4a": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    "matroska": {"matroska", "webm"},
    "ogg": {"ogg"},
    "flac": {"flac"},
    "mp3": {"mp3"},
    "aac": {"aac"},
}

_MIME = {
    ("VIDEO", "mov"): "video/quicktime",
    ("AUDIO", "mov"): "audio/mp4",
    ("VIDEO", "mp4"): "video/mp4",
    ("AUDIO", "mp4"): "audio/mp4",
    ("VIDEO", "webm"): "video/webm",
    ("AUDIO", "webm"): "audio/webm",
    ("VIDEO", "matroska"): "video/x-matroska",
    ("AUDIO", "matroska"): "audio/x-matroska",
    ("VIDEO", "avi"): "video/x-msvideo",
    ("VIDEO", "ogg"): "video/ogg",
    ("AUDIO", "ogg"): "audio/ogg",
    ("AUDIO", "wav"): "audio/wav",
    ("AUDIO", "flac"): "audio/flac",
    ("AUDIO", "mp3"): "audio/mpeg",
    ("AUDIO", "aac"): "audio/aac",
}


def _reject(message: str, details=None) -> NextronError:
    return NextronError(415, ErrorCode.INVALID_MEDIA_FORMAT, message, details)


def _identify_image(path: Path, hint: str) -> MediaIdentification:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:  # verify() leaves the image unusable; reopen to decode
            image.load()
            pillow_format = image.format
    except Image.DecompressionBombError as exc:
        raise _reject("The image's pixel count exceeds the safety limit") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise _reject("The file has an image signature but does not decode as an image") from exc
    if pillow_format not in IMAGE_FORMATS or pillow_format != hint:
        raise _reject("The image format does not match its file signature", {"signature": hint, "decoded": pillow_format})
    return MediaIdentification("IMAGE", pillow_format.lower(), IMAGE_FORMATS[pillow_format])


def _identify_av(path: Path, hint: str, ffprobe: str, timeout: float) -> MediaIdentification:
    try:
        probe, _ = run_ffprobe(path, ffprobe, timeout)
    except ProbeUnavailable as exc:
        raise NextronError(
            503, ErrorCode.MEDIA_PROBE_UNAVAILABLE, "Video and audio cannot be validated because FFprobe is unavailable"
        ) from exc
    except ProbeFailed as exc:
        raise _reject("The file could not be read as video or audio", {"probe_error": str(exc)}) from exc

    format_names = set((probe.get("format", {}).get("format_name") or "").split(","))
    if not format_names & _AV_FORMATS[hint]:
        raise _reject("The container does not match its file signature", {"signature": hint, "probed": sorted(format_names)})

    streams = probe.get("streams", [])
    has_video = any(
        s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in streams
    )
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if has_video:
        media_type = "VIDEO"
    elif has_audio:
        media_type = "AUDIO"
    else:
        raise _reject("The file contains no video or audio stream")

    # One canonical container name for the record.
    if hint == "matroska":
        container = "webm" if "webm" in format_names and _is_webm(streams) else "matroska"
    elif hint in ("mp4", "m4a"):
        container = "mp4"
    else:
        container = hint
    mime = _MIME.get((media_type, container))
    if mime is None:
        raise _reject("This combination of container and stream type is not supported", {"container": container, "media_type": media_type})
    return MediaIdentification(media_type, container, mime)


def _is_webm(streams: list[dict]) -> bool:
    webm_codecs = {"vp8", "vp9", "av1", "opus", "vorbis"}
    return all(s.get("codec_name") in webm_codecs for s in streams if s.get("codec_type") in ("video", "audio"))


def identify_media(path: Path, *, ffprobe: str, timeout_seconds: float) -> MediaIdentification:
    with open(path, "rb") as stream:
        head = stream.read(64)
    signature = sniff_signature(head)
    if signature is None:
        raise _reject("The file is not a supported image, video or audio format")
    family, hint = signature
    if family == "image":
        return _identify_image(path, hint)
    return _identify_av(path, hint, ffprobe, timeout_seconds)
