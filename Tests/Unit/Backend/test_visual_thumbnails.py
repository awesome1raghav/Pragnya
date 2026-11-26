"""Web thumbnails are bounded copies fetched through NEXTRON, never browser hotlinks."""

import io
from types import SimpleNamespace

import pytest
from PIL import Image

from Backend.App.Core.Exceptions import NextronError
from Backend.App.Modules.NexSrc.SafeFetch import Refused
from Backend.App.Modules.NexSrc.VisualThumbnails import remember, render


def test_preview_uses_temporary_token_and_strips_source_metadata():
    source = Image.new("RGB", (640, 480), "teal")
    source.getexif()[271] = "Camera name"
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", exif=source.getexif())
    matches = [{"image_url": "https://example.org/photo.jpg"}]
    remember(matches)
    token = matches[0]["thumbnail_token"]
    seen = []

    def fake_fetch(url, *, max_bytes, timeout):
        seen.append((url, max_bytes, timeout))
        return SimpleNamespace(status=200, body=buffer.getvalue())

    with Image.open(io.BytesIO(render(token, fetcher=fake_fetch))) as preview:
        assert preview.format == "JPEG"
        assert preview.width <= 240 and preview.height <= 160
        assert not preview.getexif()
    assert seen == [("https://example.org/photo.jpg", 2 * 1024 * 1024, 8)]


def test_unknown_or_refused_preview_is_unavailable():
    with pytest.raises(NextronError) as unknown:
        render("missing")
    assert unknown.value.status_code == 404
    matches = [{"image_url": "http://127.0.0.1/internal"}]
    remember(matches)

    def refused(*args, **kwargs):
        raise Refused("internal address")

    with pytest.raises(NextronError) as rejected:
        render(matches[0]["thumbnail_token"], fetcher=refused)
    assert rejected.value.status_code == 404
