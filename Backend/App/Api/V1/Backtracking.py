"""First NEX-BTK vertical slice: local, evidence-backed video comparison."""
import hashlib
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import NextronError
from Backend.App.Dependencies import get_db_session, get_settings_dependency, get_storage
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexEvd.Service import get_evidence
from Backend.App.Modules.NexBtk.VideoMatch import VERSION, compare
from Backend.App.Modules.NexBtk.Verify import VERSION as VERIFY_VERSION, verify
from Backend.App.Modules.NexFpm import Fingerprints as F
from Backend.App.Schemas.Common import envelope
from Backend.App.Config import Settings
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Contracts.ExecutionStates import JobType
from Backend.App.Dependencies import get_actor
from Backend.App.Modules.NexBtk.Expansion import MAX_COMPARISONS, MAX_VIDEOS
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import (AnalysisJob, BacktrackingComparison, Evidence, MediaFingerprint,
                                        Review, SourceObservation, SourceRecord)

router = APIRouter(tags=["Backtracking (NEX-BTK)"])


class CompareRequest(BaseModel):
    seed_evidence_id: uuid.UUID
    candidate_evidence_id: uuid.UUID


class ExpandRequest(BaseModel):
    seed_evidence_id: uuid.UUID
    max_comparisons: int = Field(default=MAX_COMPARISONS, ge=1, le=MAX_COMPARISONS)


@router.post("/cases/{case_id}/backtracking/expand", status_code=202)
def enqueue_expansion(case_id: uuid.UUID, body: ExpandRequest,
                      session: Session = Depends(get_db_session),
                      settings: Settings = Depends(get_settings_dependency),
                      actor: str = Depends(get_actor)):
    Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))
    videos = session.scalars(select(Evidence).where(Evidence.case_id == case_id, Evidence.media_type == "VIDEO")
                             .order_by(Evidence.evidence_number).limit(MAX_VIDEOS + 1)).all()
    if len(videos) > MAX_VIDEOS:
        raise NextronError(422, "EXPANSION_LIMIT", f"At most {MAX_VIDEOS} local videos can be expanded in one run")
    if body.seed_evidence_id not in {e.id for e in videos}:
        raise NextronError(404, "EVIDENCE_NOT_IN_CASE", "Seed must be a video in this case")
    params = {"seed_evidence_id": str(body.seed_evidence_id), "max_comparisons": body.max_comparisons,
              "videos": {str(e.id): e.sha256 for e in videos}}
    existing = session.scalar(select(AnalysisJob).where(AnalysisJob.case_id == case_id,
                              AnalysisJob.job_type == JobType.BACKTRACK_EXPANSION.value,
                              AnalysisJob.parameters == params,
                              AnalysisJob.state.in_(("QUEUED", "RUNNING", "COMPLETED")))
                              .order_by(AnalysisJob.created_at.desc()).limit(1))
    reused = existing is not None
    if existing is None:
        existing = JobService.enqueue(session, job_type=JobType.BACKTRACK_EXPANSION, case_id=case_id,
                                      requested_by=actor, settings=settings, evidence_id=body.seed_evidence_id,
                                      parameters=params)
        session.commit()
    return envelope({"job_id": str(existing.id), "state": existing.state, "reused": reused},
                    "Local expansion queued")


def _record_data(record: BacktrackingComparison, hashes: dict[uuid.UUID, str]) -> dict:
    return {"id": str(record.id), "case_id": str(record.case_id),
            "seed_evidence_id": str(record.seed_evidence_id), "candidate_evidence_id": str(record.candidate_evidence_id),
            "seed_sha256": record.seed_sha256, "candidate_sha256": record.candidate_sha256,
            "created_at": record.created_at.isoformat(),
            "current": (hashes.get(record.seed_evidence_id) == record.seed_sha256 and
                        hashes.get(record.candidate_evidence_id) == record.candidate_sha256 and
                        record.algorithm in (VERSION, VERIFY_VERSION) and record.fingerprint_algorithm == F.ALGORITHM), **record.result}


@router.get("/cases/{case_id}/backtracking/source-occurrences")
def list_source_occurrences(case_id: uuid.UUID, page: int = Query(default=1, ge=1),
                            page_size: int = Query(default=50, ge=1, le=100),
                            session: Session = Depends(get_db_session)):
    """Read NEX-SRC observations; inaccessible URLs remain metadata, not comparison inputs."""
    get_case(session, case_id)
    rows = session.execute(
        select(SourceRecord, SourceObservation, Evidence)
        .outerjoin(SourceObservation, SourceObservation.source_id == SourceRecord.id)
        .outerjoin(Evidence, Evidence.id == SourceObservation.evidence_id)
        .where(SourceRecord.case_id == case_id)
        .order_by(SourceRecord.source_number, SourceObservation.revision)
        .offset((page - 1) * page_size).limit(page_size)
    )
    occurrences = []
    for source, observation, evidence in rows:
        outcome = observation.outcome if observation else source.state
        local_video = evidence is not None and evidence.case_id == case_id and evidence.media_type == "VIDEO"
        occurrences.append({
            "source_id": str(source.id), "source_number": source.display_number,
            "observation_id": str(observation.id) if observation else None,
            "revision": observation.revision if observation else source.revision,
            "url": source.normalized_url, "final_url": observation.final_url if observation else None,
            "platform": source.platform, "outcome": outcome,
            "detail": observation.detail if observation else source.state_detail,
            "claimed_publication_time": ((observation.metadata_ or {}).get("claimed_publication_time")
                                         if observation else source.claimed_publication_time),
            "observed_at": observation.retrieved_at.isoformat() if observation else None,
            "preserved_evidence_id": str(evidence.id) if evidence and evidence.case_id == case_id else None,
            "backtracking_access": "LOCAL_VIDEO" if local_video else (
                "UNSUPPORTED_MEDIA" if evidence is not None else "METADATA_ONLY"),
        })
    return envelope({"case_id": str(case_id), "page": page, "page_size": page_size,
                     "source_occurrences": occurrences}, "NEX-SRC source occurrences")


@router.get("/cases/{case_id}/backtracking/candidates")
def list_video_candidates(case_id: uuid.UUID, seed_evidence_id: uuid.UUID | None = None,
                          all_media: bool = False,
                          session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    if seed_evidence_id is not None:
        seed = get_evidence(session, seed_evidence_id)
        if seed.case_id != case_id or (not all_media and seed.media_type != "VIDEO"):
            raise NextronError(404, "EVIDENCE_NOT_IN_CASE", "Seed is not eligible in this case")
    statement = (select(Evidence, MediaFingerprint.id).outerjoin(
        MediaFingerprint, (MediaFingerprint.evidence_id == Evidence.id) &
        (MediaFingerprint.kind == "VIDEO_FRAME_DHASH") & (MediaFingerprint.algorithm == F.ALGORITHM))
        .where(Evidence.case_id == case_id)
        .order_by(Evidence.evidence_number))
    if not all_media:
        statement = statement.where(Evidence.media_type == "VIDEO")
    if seed_evidence_id is not None:
        statement = statement.where(Evidence.id != seed_evidence_id)
    items = [{"evidence_id": str(e.id), "display_number": e.display_number, "filename": e.original_filename,
              "media_type": e.media_type,
              "sha256": e.sha256, "size_bytes": e.size_bytes, "fingerprint_indexed": fp_id is not None}
             for e, fp_id in session.execute(statement)]
    return envelope({"case_id": str(case_id), "candidates": items}, "Case video inventory")


@router.get("/cases/{case_id}/backtracking/comparisons")
def list_comparisons(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    records = session.scalars(select(BacktrackingComparison).where(BacktrackingComparison.case_id == case_id)
                              .order_by(BacktrackingComparison.created_at.desc()).limit(200)).all()
    ids = {id for r in records for id in (r.seed_evidence_id, r.candidate_evidence_id)}
    hashes = dict(session.execute(select(Evidence.id, Evidence.sha256).where(Evidence.id.in_(ids))).all()) if ids else {}
    return envelope({"case_id": str(case_id), "comparisons": [_record_data(r, hashes) for r in records]},
                    "Local comparison history")


@router.get("/cases/{case_id}/backtracking/comparisons/{comparison_id}")
def comparison_inspector(case_id: uuid.UUID, comparison_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    record = session.get(BacktrackingComparison, comparison_id)
    if record is None or record.case_id != case_id:
        raise NextronError(404, "COMPARISON_NOT_IN_CASE", "Comparison is not in this case")
    hashes = dict(session.execute(select(Evidence.id, Evidence.sha256).where(
        Evidence.id.in_((record.seed_evidence_id, record.candidate_evidence_id)))).all())
    review = session.scalar(select(Review).where(Review.case_id == case_id,
                            Review.subject_type == "BACKTRACK_COMPARISON", Review.subject_id == record.id)
                            .order_by(Review.version.desc()).limit(1))
    return envelope({**_record_data(record, hashes), "review": {
        "decision": review.decision, "rationale": review.rationale, "reviewer": review.reviewer,
        "review_id": str(review.id), "version": review.version} if review else None}, "Comparison evidence inspector")


@router.get("/cases/{case_id}/backtracking/overview")
def backtracking_overview(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    evidence = session.scalars(select(Evidence).where(Evidence.case_id == case_id)
                               .order_by(Evidence.evidence_number)).all()
    video_ids = {e.id for e in evidence if e.media_type == "VIDEO"}
    records = session.scalars(select(BacktrackingComparison).where(BacktrackingComparison.case_id == case_id)
                              .order_by(BacktrackingComparison.created_at.desc()).limit(500)).all()
    hashes = {e.id: e.sha256 for e in evidence}
    ids = [r.id for r in records]
    reviews = session.scalars(select(Review).where(Review.case_id == case_id,
                              Review.subject_type == "BACKTRACK_COMPARISON", Review.subject_id.in_(ids))
                              .order_by(Review.version.desc())).all() if ids else []
    decisions = {}
    for review in reviews:
        decisions.setdefault(review.subject_id, review.decision)
    covered = session.execute(select(BacktrackingComparison.seed_evidence_id, BacktrackingComparison.candidate_evidence_id,
                                     BacktrackingComparison.seed_sha256, BacktrackingComparison.candidate_sha256,
                                     BacktrackingComparison.algorithm, BacktrackingComparison.fingerprint_algorithm)
                              .where(BacktrackingComparison.case_id == case_id)).all()
    pairs = {frozenset((a, b)) for a, b, ah, bh, algorithm, fingerprint in covered
             if a in video_ids and b in video_ids and hashes.get(a) == ah and hashes.get(b) == bh
             and algorithm in (VERSION, VERIFY_VERSION) and fingerprint == F.ALGORITHM}
    possible = len(video_ids) * (len(video_ids) - 1) // 2
    edges = [{"comparison_id": str(r.id), "from": str(r.seed_evidence_id), "to": str(r.candidate_evidence_id),
              "status": r.status, "review_decision": decisions.get(r.id), "algorithm": r.algorithm,
              "coverage_seed_percent": r.result.get("submitted_coverage_percent"),
              "coverage_candidate_percent": r.result.get("candidate_coverage_percent")}
             for r in records if r.status == "CANDIDATE_MATCH" and _record_data(r, hashes)["current"]]
    total_records = session.scalar(select(func.count()).select_from(BacktrackingComparison)
                                   .where(BacktrackingComparison.case_id == case_id)) or 0
    return envelope({"case_id": str(case_id), "nodes": [{"evidence_id": str(e.id),
                    "label": e.display_number, "filename": e.original_filename} for e in evidence],
                    "edges": edges, "coverage": {"compared_pairs": len(pairs), "possible_video_pairs": possible,
                    "pair_percent": round(100 * len(pairs) / possible, 2) if possible else None},
                    "comparison_records": total_records, "shown_records": len(records),
                    "truncated": total_records > len(records)}, "Backtracking investigation overview")


@router.post("/cases/{case_id}/backtracking/compare")
async def compare_preserved_videos(case_id: uuid.UUID, body: CompareRequest,
                                   session: Session = Depends(get_db_session),
                                   storage: LocalStorage = Depends(get_storage),
                                   settings: Settings = Depends(get_settings_dependency)):
    Lifecycle.ensure_writable(get_case(session, case_id))
    if body.seed_evidence_id == body.candidate_evidence_id:
        raise NextronError(422, "INVALID_COMPARISON", "Choose two distinct evidence items")
    seed, candidate = get_evidence(session, body.seed_evidence_id), get_evidence(session, body.candidate_evidence_id)
    if seed.case_id != case_id or candidate.case_id != case_id:
        raise NextronError(404, "EVIDENCE_NOT_IN_CASE", "Both evidence items must belong to the case")
    if seed.media_type != "VIDEO" or candidate.media_type != "VIDEO":
        raise NextronError(422, "VIDEO_REQUIRED", "This first backtracking slice compares preserved videos")
    paths = [storage.local_path(e.storage_key) for e in (seed, candidate)]
    for evidence, path in zip((seed, candidate), paths):
        if path is None or not path.is_file():
            raise NextronError(410, "EVIDENCE_FILE_MISSING", "A preserved original is unavailable")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != evidence.sha256:
                raise NextronError(409, "INTEGRITY_MISMATCH", "A preserved original failed integrity verification")
    key = {"case_id": case_id, "seed_evidence_id": seed.id, "candidate_evidence_id": candidate.id,
           "seed_sha256": seed.sha256, "candidate_sha256": candidate.sha256,
           "algorithm": VERSION, "fingerprint_algorithm": F.ALGORITHM}
    existing = session.scalar(select(BacktrackingComparison).filter_by(**key))
    if existing is not None:
        return envelope(_record_data(existing, {seed.id: seed.sha256, candidate.id: candidate.sha256}),
                        "Local video comparison retrieved")
    result = await run_in_threadpool(compare, paths[0], paths[1], ffprobe=settings.FFPROBE_PATH,
                                     timeout=min(settings.MODULE_TIMEOUT_SECONDS, 180))
    Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))
    session.execute(insert(BacktrackingComparison).values(id=uuid.uuid4(), **key, status=result["status"], result=result)
                    .on_conflict_do_nothing(constraint="uq_btk_comparison_inputs"))
    session.commit()
    record = session.scalar(select(BacktrackingComparison).filter_by(**key))
    return envelope(_record_data(record, {seed.id: seed.sha256, candidate.id: candidate.sha256}),
                    "Local video comparison completed")


@router.post("/cases/{case_id}/backtracking/verify")
async def verify_preserved_media(case_id: uuid.UUID, body: CompareRequest,
                                 session: Session = Depends(get_db_session),
                                 storage: LocalStorage = Depends(get_storage),
                                 settings: Settings = Depends(get_settings_dependency)):
    Lifecycle.ensure_writable(get_case(session, case_id))
    if body.seed_evidence_id == body.candidate_evidence_id:
        raise NextronError(422, "INVALID_COMPARISON", "Choose two distinct evidence items")
    seed, candidate = get_evidence(session, body.seed_evidence_id), get_evidence(session, body.candidate_evidence_id)
    if seed.case_id != case_id or candidate.case_id != case_id:
        raise NextronError(404, "EVIDENCE_NOT_IN_CASE", "Both evidence items must belong to the case")
    paths = [storage.local_path(e.storage_key) for e in (seed, candidate)]
    for evidence, path in zip((seed, candidate), paths):
        if path is None or not path.is_file():
            raise NextronError(410, "EVIDENCE_FILE_MISSING", "A preserved original is unavailable")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != evidence.sha256:
                raise NextronError(409, "INTEGRITY_MISMATCH", "A preserved original failed integrity verification")
    key = {"case_id": case_id, "seed_evidence_id": seed.id, "candidate_evidence_id": candidate.id,
           "seed_sha256": seed.sha256, "candidate_sha256": candidate.sha256,
           "algorithm": VERIFY_VERSION, "fingerprint_algorithm": F.ALGORITHM}
    record = session.scalar(select(BacktrackingComparison).filter_by(**key))
    if record is None:
        result = await run_in_threadpool(verify, paths[0], paths[1], seed.media_type, candidate.media_type,
                                         ffprobe=settings.FFPROBE_PATH, timeout=min(settings.MODULE_TIMEOUT_SECONDS, 180))
        Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))
        session.execute(insert(BacktrackingComparison).values(id=uuid.uuid4(), **key, status=result["status"], result=result)
                        .on_conflict_do_nothing(constraint="uq_btk_comparison_inputs"))
        session.commit()
        record = session.scalar(select(BacktrackingComparison).filter_by(**key))
    return envelope(_record_data(record, {seed.id: seed.sha256, candidate.id: candidate.sha256}),
                    "Local media verification completed")
