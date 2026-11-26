"""Opt-in Google Lens lookup through SerpApi's free plan.

Only a derived, metadata-free search copy leaves the machine. Results are leads,
never verified source records. Provider responses are never trusted as HTML.
"""

import io
import logging

import httpx
from PIL import Image

from Backend.App.Core.Exceptions import NextronError

MAX_PROVIDER_BYTES = 500_000
ORIGIN = "https://serpapi.com"
# SerpApi requires the key in query parameters and httpx otherwise logs full URLs at INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)


def search_copy(image: Image.Image) -> bytes:
    """Fit SerpApi's 500 KB upload limit without touching the evidence original."""
    image = image.convert("RGB")
    for edge in (1200, 960, 768, 640, 512, 384, 256):
        candidate = image.copy()
        candidate.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        for quality in (85, 72, 58):
            output = io.BytesIO()
            candidate.save(output, format="JPEG", quality=quality, optimize=True)
            if len(output.getvalue()) <= MAX_PROVIDER_BYTES:
                return output.getvalue()
    raise NextronError(422, "WEB_IMAGE_TOO_COMPLEX", "The image could not be prepared under the web provider's 500 KB limit")


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        url = httpx.URL(value)
        if url.scheme in {"https", "http"} and url.host and not url.username and not url.password:
            return value
    except (ValueError, TypeError):
        pass
    return None


def parse_matches(payload: dict, top_k: int) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("error"):
        raise NextronError(502, "WEB_SEARCH_FAILED", "Web search provider returned an error")
    state = (payload.get("search_metadata") or {}).get("status")
    if state != "Success":
        raise NextronError(502, "WEB_SEARCH_FAILED", "Web search provider did not complete the search")
    candidates = payload.get("visual_matches", [])
    if not isinstance(candidates, list):
        raise NextronError(502, "WEB_SEARCH_FAILED", "Web search provider returned invalid results")
    results, seen = [], set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        page = _safe_url(item.get("link"))
        image = _safe_url(item.get("image"))
        if not page and not image:
            continue
        key = (page, image)
        if key in seen:
            continue
        seen.add(key)
        results.append({"page_url": page, "image_url": image,
                        "title": str(item.get("title") or "Web image match")[:300],
                        "match_type": "EXACT_MATCH_REPORTED" if item.get("exact_matches") is True else "VISUAL_MATCH",
                        "score": None, "score_kind": None})
        if len(results) >= top_k:
            break
    return results


def _json_response(response: httpx.Response) -> dict:
    try:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid response")
        return payload
    except (httpx.HTTPStatusError, ValueError) as exc:
        code = 429 if response.status_code == 429 else 502
        raise NextronError(code, "WEB_SEARCH_LIMIT" if code == 429 else "WEB_SEARCH_FAILED",
                           "Web search quota or rate limit reached" if code == 429 else "Web search provider is unavailable") from exc


def search(image: Image.Image, api_key: str, top_k: int, *, transport=None) -> list[dict]:
    if not api_key:
        raise NextronError(503, "WEB_SEARCH_DISABLED", "SerpApi is not configured")
    image_bytes = search_copy(image)
    try:
        with httpx.Client(base_url=ORIGIN, timeout=httpx.Timeout(40, connect=5), follow_redirects=False,
                          transport=transport) as client:
            # Fail closed on paid plans or depleted free quota; don't create billable searches.
            account = _json_response(client.get("/account.json", params={"api_key": api_key}))
            if account.get("error"):
                raise NextronError(502, "WEB_SEARCH_FAILED", "Web search account check failed")
            if not str(account.get("plan_name", "")).lower().startswith("free") or account.get("plan_monthly_price") != 0:
                raise NextronError(409, "WEB_SEARCH_FREE_PLAN_REQUIRED", "Web search is enabled only for SerpApi's free plan")
            if not isinstance(account.get("plan_searches_left"), int) or account["plan_searches_left"] <= 0:
                raise NextronError(429, "WEB_SEARCH_LIMIT", "No free web searches remain this month")
            if isinstance(account.get("account_rate_limit_per_hour"), int) and isinstance(account.get("this_hour_searches"), int):
                if account["this_hour_searches"] >= account["account_rate_limit_per_hour"]:
                    raise NextronError(429, "WEB_SEARCH_LIMIT", "Free web search hourly limit reached")
            upload = _json_response(client.post("/image", data={"api_key": api_key},
                                                files={"image": ("search-copy.jpg", image_bytes, "image/jpeg")}))
            image_id = upload.get("image_id")
            if not isinstance(image_id, str) or not image_id or upload.get("error"):
                raise NextronError(502, "WEB_SEARCH_FAILED", "Web search provider could not accept the image")
            payload = _json_response(client.get("/search.json", params={"api_key": api_key, "engine": "google_lens",
                                                                     "image_id": image_id, "type": "all", "safe": "active"}))
            return parse_matches(payload, top_k)
    except httpx.HTTPError as exc:
        raise NextronError(502, "WEB_SEARCH_FAILED", "Web search provider is unreachable") from exc
