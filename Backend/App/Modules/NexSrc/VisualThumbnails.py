"""Short-lived, SSRF-checked previews for explicitly requested web matches."""

import io
import secrets
import threading
import time

from PIL import Image, ImageOps, UnidentifiedImageError

from Backend.App.Core.Exceptions import NextronError
from Backend.App.Modules.NexSrc.SafeFetch import FetchError, Refused, fetch

_TTL_SECONDS = 600
_MAX_TOKENS = 500
_MAX_BYTES = 2 * 1024 * 1024
_MAX_PIXELS = 24_000_000
_tokens: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()


def remember(matches: list[dict]) -> None:
    """Grant only returned image URLs a temporary preview token."""
    now = time.monotonic()
    with _lock:
        for token, (expiry, _) in list(_tokens.items()):
            if expiry <= now:
                _tokens.pop(token, None)
        for match in matches:
            url = match.get("image_url")
            if not url:
                continue
            if len(_tokens) >= _MAX_TOKENS:
                _tokens.pop(next(iter(_tokens)))
            token = secrets.token_urlsafe(24)
            _tokens[token] = (now + _TTL_SECONDS, url)
            match["thumbnail_token"] = token


def render(token: str, *, fetcher=fetch) -> bytes:
    with _lock:
        entry = _tokens.get(token)
        if entry and entry[0] <= time.monotonic():
            _tokens.pop(token, None)
            entry = None
    if entry is None:
        raise NextronError(404, "THUMBNAIL_UNAVAILABLE", "This web preview is no longer available")
    try:
        fetched = fetcher(entry[1], max_bytes=_MAX_BYTES, timeout=8)
        if fetched.status != 200 or not fetched.body:
            raise ValueError("No image returned")
        with Image.open(io.BytesIO(fetched.body)) as source:
            if source.width * source.height > _MAX_PIXELS:
                raise ValueError("Image exceeds the preview pixel limit")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((240, 160), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=78, optimize=True)
        return output.getvalue()
    except (FetchError, Refused, ValueError, UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise NextronError(404, "THUMBNAIL_UNAVAILABLE", "The web image preview could not be loaded") from exc
