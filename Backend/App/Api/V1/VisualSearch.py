"""Search an investigation's indexed images from a screenshot, image or safe URL."""

import json
import uuid
import hashlib

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import NextronError
from Backend.App.Dependencies import get_db_session, get_settings_dependency
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexFpm.Embeddings import ImageEncoder, decode_image
from Backend.App.Modules.NexFpm.VisualSearch import search_case
from Backend.App.Projections.QdrantImages import QdrantImages
from Backend.App.Modules.NexSrc.SafeFetch import FetchError, Refused, fetch
from Backend.App.Modules.NexSrc.SerpApiVisualSearch import search as web_search
from Backend.App.Modules.NexSrc.VisualThumbnails import remember, render
from Backend.App.Schemas.Common import envelope
from Database.PostgreSQL.Models import VisualEmbedding

router = APIRouter(tags=["Visual Search (NEX-FPM)"])


@router.get("/visual-search/thumbnails/{token}")
async def thumbnail(token: str):
    image = await run_in_threadpool(render, token)
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600",
                                                          "X-Content-Type-Options": "nosniff"})


@router.get("/visual-search/status")
def visual_status(settings: Settings = Depends(get_settings_dependency), session: Session = Depends(get_db_session)):
    indexed = session.scalar(select(func.count()).select_from(VisualEmbedding)) or 0
    reachable, points = False, None
    if settings.QDRANT_URL:
        try:
            points = QdrantImages(settings.QDRANT_URL, settings.QDRANT_API_KEY.get_secret_value()).count()
            reachable = True
        except Exception:
            pass
    return envelope({"local": {"configured": bool(settings.QDRANT_URL),
                                "model_ready": ImageEncoder(settings.VISUAL_MODEL_PATH).ready,
                                "reachable": reachable, "indexed_in_postgres": indexed, "points_in_qdrant": points},
                     "web": {"configured": bool(settings.WEB_VISUAL_SEARCH_ENABLED and settings.SERPAPI_API_KEY.get_secret_value()),
                             "provider": "serpapi_google_lens"},
                     "max_bytes": settings.VISUAL_SEARCH_MAX_BYTES}, "Visual search availability")


@router.post("/cases/{case_id}/visual-search", status_code=status.HTTP_200_OK)
async def search(case_id: uuid.UUID, request: Request, mode: str = Form("local"), url: str | None = Form(None),
                 top_k: int = Form(10), crop: str | None = Form(None), allow_external: bool = Form(False),
                 session: Session = Depends(get_db_session), settings: Settings = Depends(get_settings_dependency)):
    get_case(session, case_id)
    if mode not in {"local", "web"}:
        raise NextronError(422, "INVALID_SEARCH_MODE", "Choose local or web search")
    if mode == "web":
        if not settings.WEB_VISUAL_SEARCH_ENABLED or not settings.SERPAPI_API_KEY.get_secret_value():
            raise NextronError(503, "WEB_SEARCH_DISABLED", "SerpApi is not configured")
        if not allow_external:
            raise NextronError(403, "WEB_SEARCH_CONSENT_REQUIRED", "Confirm that a derived image may be sent to SerpApi and Google Lens")
    if not 1 <= top_k <= 50:
        raise NextronError(422, "INVALID_SEARCH_LIMIT", "top_k must be between 1 and 50")
    form = await request.form()
    upload = form.get("file")
    if bool(upload) == bool(url):
        raise NextronError(422, "INVALID_SEARCH_IMAGE", "Provide exactly one image file or URL")
    if url:
        try:
            result = await run_in_threadpool(fetch, url, max_bytes=settings.VISUAL_SEARCH_MAX_BYTES, timeout=10)
            if result.status != 200:
                raise ValueError("Image URL did not return HTTP 200")
            raw = result.body or b""
        except (Refused, FetchError, ValueError) as exc:
            raise NextronError(422, "INVALID_SEARCH_URL", str(exc)) from exc
    else:
        raw = await upload.read(settings.VISUAL_SEARCH_MAX_BYTES + 1)
        if len(raw) > settings.VISUAL_SEARCH_MAX_BYTES:
            raise NextronError(413, "SEARCH_IMAGE_TOO_LARGE", "Search image exceeds the byte limit")
    try:
        rectangle = json.loads(crop) if crop else None
    except json.JSONDecodeError as exc:
        raise NextronError(422, "INVALID_SEARCH_CROP", "Crop must be a JSON rectangle") from exc
    if mode == "local":
        return envelope(await run_in_threadpool(search_case, session, settings, case_id, raw, crop=rectangle, top_k=top_k),
                        "Local related images")
    try:
        image = decode_image(raw, rectangle)
    except ValueError as exc:
        raise NextronError(422, "INVALID_SEARCH_IMAGE", str(exc)) from exc
    matches = await run_in_threadpool(web_search, image, settings.SERPAPI_API_KEY.get_secret_value(), top_k)
    remember(matches)
    return envelope({"provider": "serpapi_google_lens", "scope": "web", "query_sha256": hashlib.sha256(raw).hexdigest(),
                     "matches": matches, "limitations": ["Results cover pages returned by Google Lens through SerpApi, not the entire web.",
                                                     "Exact-match labels are provider reports; verify the page and image before drawing conclusions."]},
                    "Web image leads")
