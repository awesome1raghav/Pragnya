"""Official Google Web Detection adapter; no scraping and no implied internet-wide coverage."""

import base64
import io
from urllib.parse import urlsplit

import httpx
from PIL import Image

from Backend.App.Core.Exceptions import NextronError


def safe_link(value) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def parse_matches(annotation: dict, top_k: int) -> list[dict]:
    rows, seen = [], set()

    def add(image, kind, page=None):
        image_url = safe_link(image.get("url"))
        page_url = safe_link((page or {}).get("url"))
        key = (image_url, page_url)
        if not any(key) or key in seen:
            return
        seen.add(key)
        rows.append({"image_url": image_url, "page_url": page_url,
                     "title": str((page or {}).get("pageTitle", ""))[:500] or None,
                     "match_type": kind, "score": None, "score_kind": None})

    # Google documents WebImage.score as deprecated; never invent a percentage from it.
    for page in annotation.get("pagesWithMatchingImages", []):
        for key, kind in (("fullMatchingImages", "FULL_MATCH"), ("partialMatchingImages", "PARTIAL_MATCH")):
            for image in page.get(key, []):
                add(image, kind, page)
        if not page.get("fullMatchingImages") and not page.get("partialMatchingImages"):
            add({}, "MATCHING_PAGE", page)
    for key, kind in (("fullMatchingImages", "FULL_MATCH"), ("partialMatchingImages", "PARTIAL_MATCH"),
                      ("visuallySimilarImages", "VISUALLY_SIMILAR")):
        for image in annotation.get(key, []):
            add(image, kind)
    return rows[:top_k]


def search(image: Image.Image, api_key: str, top_k: int, *, transport=None) -> list[dict]:
    # EXIF/private metadata is not transmitted. This is a derived query, never the stored original.
    image = image.copy()
    image.thumbnail((1600, 1600))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    payload = {"requests": [{"image": {"content": base64.b64encode(buffer.getvalue()).decode("ascii")},
                             "features": [{"type": "WEB_DETECTION", "maxResults": top_k}]}]}
    try:
        with httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False, transport=transport) as client:
            response = client.post("https://vision.googleapis.com/v1/images:annotate", json=payload,
                                   headers={"X-Goog-Api-Key": api_key})
            response.raise_for_status()
            replies = response.json().get("responses", [])
            if not replies or replies[0].get("error"):
                raise ValueError("Provider returned an error")
            return parse_matches(replies[0].get("webDetection", {}), top_k)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        # Never reflect Google's credential/account details or raw HTTP requests to the browser.
        raise NextronError(502, "WEB_SEARCH_FAILED", "Web image search failed; check provider credentials, quota or availability") from exc
