"""NEX-MET EXIF decoding into JSON-safe values. Metadata is recorded, not trusted."""

from fractions import Fraction
from typing import Any

from PIL import ExifTags, Image, TiffImagePlugin

_EXIF_IFD = ExifTags.IFD.Exif
_GPS_IFD = ExifTags.IFD.GPSInfo
_LARGE_TAGS = {"MakerNote", "UserComment", "PrintImageMatching"}
MAX_BYTES_INLINE = 64
MAX_STRING = 2000

# EXIF tags that carry claimed capture/edit times; surfaced separately and labelled unverified.
TIMESTAMP_TAGS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime", "OffsetTimeOriginal", "OffsetTime")


def json_safe(value: Any) -> Any:
    if isinstance(value, TiffImagePlugin.IFDRational):
        if value.denominator == 0:
            return None
        return float(Fraction(value.numerator, value.denominator))
    if isinstance(value, bytes):
        if len(value) <= MAX_BYTES_INLINE:
            return {"bytes_hex": value.hex()}
        return {"bytes_length": len(value)}
    if isinstance(value, str):
        return value.replace("\x00", "").strip()[:MAX_STRING]
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value[:256]]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_STRING]


def _named(ifd: dict, names: dict[int, str]) -> dict[str, Any]:
    out = {}
    for tag_id, value in ifd.items():
        name = names.get(tag_id, f"Tag0x{tag_id:04X}")
        out[name] = {"bytes_length": len(value)} if name in _LARGE_TAGS and isinstance(value, bytes) else json_safe(value)
    return out


def analyze(image: Image.Image) -> dict[str, Any]:
    exif = image.getexif()
    if not exif:
        return {"present": False, "tags": {}, "gps": {}, "embedded_timestamps": {}}
    tags = _named({k: v for k, v in exif.items() if k not in (_EXIF_IFD, _GPS_IFD)}, ExifTags.TAGS)
    tags |= _named(exif.get_ifd(_EXIF_IFD), ExifTags.TAGS)
    gps = _named(exif.get_ifd(_GPS_IFD), ExifTags.GPSTAGS)
    return {
        "present": True,
        "tags": tags,
        "gps": gps,
        "embedded_timestamps": {name: tags[name] for name in TIMESTAMP_TAGS if name in tags},
    }
