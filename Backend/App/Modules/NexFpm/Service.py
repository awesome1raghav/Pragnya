"""NEX-FPM in T-MIR: fingerprint one evidence item, store the fingerprints, search the case for similar media.

The candidate search covers the evidence of the same investigation (the corpus an investigator assembled, including
media retrieved from sources); it never reaches outside NEXTRON. Matches are OBSERVATION findings with the distance
as a DISTANCE score; NEX-MOC turns them into candidate relationships.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind
from Backend.App.Modules.Engine import EngineOutput
from Backend.App.Modules.NexFpm import Fingerprints as F
from Database.PostgreSQL.Models import Evidence, MediaFingerprint

MODULE = "NEX-FPM"
VERSION = F.ALGORITHM
PARAMETERS = {"phash_match": F.PHASH_MATCH, "dhash_match": F.DHASH_MATCH, "audio_ber_match": F.AUDIO_BER_MATCH,
              "audio_block": F.AUDIO_BLOCK, "video_fps": F.VIDEO_FPS, "max_frames": F.MAX_FRAMES}
_LIMITS = {
    "SAME_CONTENT_VARIANT": "On the controlled set, 9 % of benign variants (mostly 10 % crops) were not matched; heavy crops, overlays and mirroring are missed",
    "NEAR_DUPLICATE": "Near-identical perceptual hashes; different files can still share them if they show the same scene",
    "FRAME_OF_VIDEO": "Frames are sampled once per second; a still taken between samples can be missed, and flat graphics (slides, test patterns) give unstable hashes",
    "SHARED_VIDEO_SEGMENT": "Static or slowly changing footage matches easily; the offset is a median over matched frames",
    "SHARED_AUDIO": "The same music or broadcast audio in different videos also matches",
}


def compute(path, media_type: str, *, settings) -> dict:
    if media_type == "IMAGE":
        return F.fingerprint_image(path)
    fingerprints = {}
    if media_type == "VIDEO":
        fingerprints |= F.fingerprint_video(path, ffprobe=settings.FFPROBE_PATH, timeout=settings.MODULE_TIMEOUT_SECONDS)
    fingerprints |= F.fingerprint_audio(path, ffprobe=settings.FFPROBE_PATH, timeout=settings.MODULE_TIMEOUT_SECONDS)
    return fingerprints


def store(session: Session, evidence: Evidence, fingerprints: dict, execution_id: uuid.UUID) -> None:
    for kind, value in fingerprints.items():
        session.execute(insert(MediaFingerprint).values(
            id=uuid.uuid4(), evidence_id=evidence.id, case_id=evidence.case_id, kind=kind, algorithm=F.ALGORITHM, value=value,
            execution_id=execution_id).on_conflict_do_nothing(constraint="uq_media_fingerprints_evidence_kind_algorithm"))
    session.flush()


def case_fingerprints(session: Session, case_id: uuid.UUID) -> dict[uuid.UUID, dict]:
    """{evidence_id: {kind: value}} for every fingerprinted evidence item in the case (this algorithm version)."""
    out: dict[uuid.UUID, dict] = {}
    for fp in session.scalars(select(MediaFingerprint).where(MediaFingerprint.case_id == case_id, MediaFingerprint.algorithm == F.ALGORITHM)):
        out.setdefault(fp.evidence_id, {})[fp.kind] = fp.value
    return out


def candidates(session: Session, evidence: Evidence, mine: dict) -> tuple[list[Finding], list[uuid.UUID]]:
    findings, related = [], []
    numbers = dict(session.execute(select(Evidence.id, Evidence.evidence_number).where(Evidence.case_id == evidence.case_id)).all())
    for other, theirs in case_fingerprints(session, evidence.case_id).items():
        if other == evidence.id:
            continue
        for m in F.compare(mine, theirs):
            related.append(other)
            distance = m.measurement.get("phash_distance", m.measurement.get("bit_error_rate"))
            findings.append(Finding(
                module_id=MODULE, evidence_ids=[evidence.id, other], assertion=Assertion.OBSERVATION, finding_type="SIMILAR_MEDIA_CANDIDATE",
                title=f"{m.kind.replace('_', ' ').capitalize()} candidate: EVD-{numbers.get(other, 0):04d} (similarity {m.similarity:.2f})",
                description="Fingerprints of the two items are close. That shows similar content, not that one was made from the other.",
                measurement=m.measurement | {"relationship": m.kind, "other_evidence_id": str(other), "offset_seconds": m.offset_seconds},
                score=float(distance) if distance is not None else None, score_kind=ScoreKind.DISTANCE if distance is not None else None,
                limitations=[_LIMITS[m.kind]], parameters=PARAMETERS,
            ))
    return findings, sorted(set(related), key=str)


def summary_finding(evidence: Evidence, fingerprints: dict) -> Finding:
    m = {kind: ({"frames": len(v["frames"])} if kind == "VIDEO_FRAME_DHASH" else {"rows": len(v["values"])} if kind == "AUDIO_SUBFINGERPRINT"
                else {"hash": v["hash"]}) for kind, v in fingerprints.items()}
    return Finding(module_id=MODULE, evidence_ids=[evidence.id], assertion=Assertion.OBSERVATION, finding_type="FINGERPRINTS_RECORDED",
                   title=f"Fingerprints recorded: {', '.join(sorted(fingerprints))}", description="Canonical fingerprints used for similarity search in this investigation.",
                   measurement=m | {"algorithm": F.ALGORITHM}, parameters=PARAMETERS)


def no_fingerprint(evidence: Evidence) -> EngineOutput:
    return EngineOutput(ExecutionState.SKIPPED, "NO_INPUT", f"{evidence.display_number} has no fingerprintable content (no frames and no audio)")
