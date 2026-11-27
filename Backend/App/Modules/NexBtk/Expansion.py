"""Bounded local expansion, checkpointed through the Job Service lease."""
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from Backend.App.Contracts.ExecutionStates import JobState
from Backend.App.Modules.NexBtk.VideoMatch import VERSION, compare
from Backend.App.Modules.NexFpm import Fingerprints as F
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import BacktrackingComparison, Evidence

MAX_VIDEOS = 100
MAX_COMPARISONS = 100


def run(factory, storage, settings, job_id, worker_id):
    with factory() as session:
        job = JobService.get_job(session, job_id)
        pinned = job.parameters["videos"]  # evidence ID -> SHA-256, captured when queued
        case_id = job.case_id
        seed = job.parameters["seed_evidence_id"]
        budget = job.parameters["max_comparisons"]
        progress = job.progress or {"frontier": [[seed, other] for other in pinned if other != seed],
                                    "seen": [], "completed": 0, "matches": 0}

    while progress["frontier"] and progress["completed"] < budget:
        with factory() as session:
            if not JobService.fence(session, job_id, worker_id):
                session.rollback()
                return None
            job = JobService.get_job(session, job_id)
            if job.cancel_requested:
                session.rollback()
                JobService.finish(session, job, worker_id, JobState.CANCELLED, progress=progress)
                return JobState.CANCELLED
            session.commit()

        a, b = progress["frontier"][0]
        pair = ":".join(sorted((a, b)))
        if pair in progress["seen"]:
            result = None
        else:
            with factory() as session:
                evidence = {str(e.id): e for e in session.scalars(
                    select(Evidence).where(Evidence.case_id == case_id, Evidence.id.in_([uuid.UUID(a), uuid.UUID(b)])))}
                if set(evidence) != {a, b} or any(evidence[k].sha256 != pinned[k] or evidence[k].media_type != "VIDEO" for k in (a, b)):
                    raise ValueError("Pinned video evidence changed or is unavailable")
                paths = [storage.local_path(evidence[k].storage_key) for k in (a, b)]
            for key, path in zip((a, b), paths):
                if path is None or not path.is_file():
                    raise FileNotFoundError("Preserved video is unavailable")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != pinned[key]:
                        raise ValueError("Preserved video failed integrity verification")
            with factory() as session:
                key = {"case_id": case_id, "seed_evidence_id": uuid.UUID(a), "candidate_evidence_id": uuid.UUID(b),
                       "seed_sha256": pinned[a], "candidate_sha256": pinned[b],
                       "algorithm": VERSION, "fingerprint_algorithm": F.ALGORITHM}
                existing = session.scalar(select(BacktrackingComparison).filter_by(**key))
                result = existing.result if existing else None
            if result is None:
                result = compare(paths[0], paths[1], ffprobe=settings.FFPROBE_PATH,
                                 timeout=min(settings.MODULE_TIMEOUT_SECONDS, 180))

        with factory() as session:
            if not JobService.fence(session, job_id, worker_id):
                session.rollback()
                return None
            job = JobService.get_job(session, job_id)
            if job.cancel_requested:
                session.rollback()
                JobService.finish(session, job, worker_id, JobState.CANCELLED, progress=progress)
                return JobState.CANCELLED
            if result is not None:
                session.execute(insert(BacktrackingComparison).values(id=uuid.uuid4(), **key, status=result["status"], result=result)
                                .on_conflict_do_nothing(constraint="uq_btk_comparison_inputs"))
            next_progress = {"frontier": progress["frontier"][1:], "seen": progress["seen"] + [pair],
                             "completed": progress["completed"] + (result is not None),
                             "matches": progress["matches"] + (result is not None and result["status"] == "CANDIDATE_MATCH")}
            if result is not None and result["status"] == "CANDIDATE_MATCH":
                pending = {":".join(sorted(p)) for p in next_progress["frontier"]} | set(next_progress["seen"])
                for other in pinned:
                    new_pair = ":".join(sorted((b, other)))
                    if other != b and new_pair not in pending:
                        next_progress["frontier"].append([b, other])
                        pending.add(new_pair)
            job.progress = next_progress
            session.commit()  # record and cursor move together; retry cannot lose either
            progress = next_progress

    with factory() as session:
        job = JobService.get_job(session, job_id)
        if job.cancel_requested:
            state = JobState.CANCELLED
        else:
            state = JobState.COMPLETED
        if not JobService.finish(session, job, worker_id, state, progress=progress):
            return None
    return state
