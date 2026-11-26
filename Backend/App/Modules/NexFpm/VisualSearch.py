"""Local image search, with PostgreSQL authoritative and Qdrant rebuildable."""

import hashlib
import time
import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import NextronError
from Backend.App.Modules.NexFpm.Embeddings import ImageEncoder, MODEL_KEY, decode_image
from Backend.App.Projections.QdrantImages import QdrantImages
from Database.PostgreSQL.Models import Evidence, VisualEmbedding


def _store_path(storage, row: Evidence) -> Path:
    path = storage.local_path(row.storage_key)
    if path is None or not path.is_file():
        raise FileNotFoundError(f"Stored image {row.id} is missing")
    return path


@lru_cache(maxsize=2)
def _encoder(path: str) -> ImageEncoder:
    return ImageEncoder(Path(path))


_projected: set[uuid.UUID] = set()  # warm-process cache only; restart replays authoritative PostgreSQL
_last_replay = 0.0


def index_pending(session: Session, storage, settings: Settings, *, batch_size: int = 16) -> int:
    """Compute missing embeddings in worker, then idempotently project committed rows."""
    global _last_replay
    if not settings.QDRANT_URL:
        return 0
    encoder = _encoder(str(settings.VISUAL_MODEL_PATH))
    if not encoder.ready:
        return 0
    pending = list(session.scalars(select(Evidence).where(Evidence.media_type == "IMAGE", ~Evidence.id.in_(
        select(VisualEmbedding.evidence_id).where(VisualEmbedding.model_key == MODEL_KEY)
    )).order_by(Evidence.received_at)))
    images, valid = [], []
    for row in pending:
        if len(valid) >= batch_size:
            break
        try:
            with _store_path(storage, row).open("rb") as stream:
                raw = stream.read(settings.VISUAL_SEARCH_MAX_BYTES + 1)
            if len(raw) <= settings.VISUAL_SEARCH_MAX_BYTES:
                images.append(decode_image(raw))
                valid.append(row)
        except (OSError, ValueError):
            continue
    if valid:
        vectors = encoder.embed(images)
        for row, vector in zip(valid, vectors):
            session.execute(insert(VisualEmbedding).values(id=uuid.uuid4(), evidence_id=row.id,
                            case_id=row.case_id, model_key=MODEL_KEY, vector=vector)
                            .on_conflict_do_nothing(constraint="uq_visual_embeddings_evidence_model"))
        session.commit()
    if time.monotonic() - _last_replay >= 300:
        _projected.clear()  # repair a lost/recreated Qdrant collection without restarting the worker
        _last_replay = time.monotonic()
    project_case = list(session.scalars(select(VisualEmbedding).where(VisualEmbedding.model_key == MODEL_KEY)
                                        .order_by(VisualEmbedding.created_at)))
    project_case = [row for row in project_case if row.evidence_id not in _projected]
    if not project_case:
        return len(valid)
    index = QdrantImages(settings.QDRANT_URL, settings.QDRANT_API_KEY.get_secret_value())
    index.ensure()
    for start in range(0, len(project_case), 128):
        chunk = project_case[start:start + 128]
        index.upsert(chunk)
        _projected.update(row.evidence_id for row in chunk)
    return len(valid)


def search_case(session: Session, settings: Settings, case_id: uuid.UUID, raw: bytes,
                *, crop: list[int] | None = None, top_k: int = 10) -> dict:
    if not settings.QDRANT_URL:
        raise NextronError(503, "VISUAL_SEARCH_UNAVAILABLE", "Local visual search is not configured")
    encoder = _encoder(str(settings.VISUAL_MODEL_PATH))
    if not encoder.ready:
        raise NextronError(503, "VISUAL_SEARCH_UNAVAILABLE", "Local visual search model is not installed")
    try:
        image = decode_image(raw, crop)
        vector = encoder.embed([image])[0]
        index = QdrantImages(settings.QDRANT_URL, settings.QDRANT_API_KEY.get_secret_value())
        points = index.query(vector, case_id, top_k)
    except ValueError as exc:
        raise NextronError(422, "INVALID_SEARCH_IMAGE", str(exc)) from exc
    except Exception as exc:
        if isinstance(exc, NextronError):
            raise
        raise NextronError(503, "VISUAL_SEARCH_UNAVAILABLE", "Local image index is unavailable") from exc
    ids = [uuid.UUID(p["payload"]["evidence_id"]) for p in points]
    evidence = {e.id: e for e in session.scalars(select(Evidence).where(Evidence.id.in_(ids), Evidence.case_id == case_id,
                                                             Evidence.media_type == "IMAGE"))}
    matches = []
    for point in points:
        row = evidence.get(uuid.UUID(point["payload"]["evidence_id"]))
        if row:
            matches.append({"evidence_id": str(row.id), "image_url": None, "page_url": None,
                            "title": row.original_filename, "match_type": "LOCAL_RELATED_IMAGE",
                            "score": round(float(point["score"]), 6), "score_kind": "COSINE_SIMILARITY"})
    return {"provider": "qdrant_siglip2", "scope": "case", "query_sha256": hashlib.sha256(raw).hexdigest(),
            "matches": matches, "limitations": ["Searches indexed images in this investigation only; similarity does not prove common origin."]}
