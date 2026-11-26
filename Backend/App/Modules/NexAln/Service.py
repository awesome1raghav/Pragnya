"""NEX-ALN Temporal Alignment (archive §4, module 12): where two related versions line up in time (or space).

For every current candidate pair NEX-MOC proposed:
  video  frames matched by pHash (one per second) and a least-squares line t_b = speed * t_a + offset through the
         matches; the overlap is the matched span in each. Tolerance: ±0.5 s (frame sampling interval / 2).
  audio  the Philips sub-fingerprints of `a` slid along `b`; the offset with the lowest bit error rate.
         Tolerance: ±0.032 s (one sub-fingerprint hop).
  image  scale from the dimensions; nothing temporal.
Results are OBSERVATIONS (measured alignment), stated with method and tolerance; NEX-TRN reads them.
"""

import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind
from Backend.App.Modules.NexFpm import Fingerprints as F
from Backend.App.Modules.NexFpm.Service import case_fingerprints
from Database.PostgreSQL.Models import Evidence, EvidenceMetadata, MediaRelationship

MODULE, VERSION = "NEX-ALN", "nextron-aln/1"
PARAMETERS = {"phash_match": F.PHASH_MATCH, "video_tolerance_s": 0.5, "audio_tolerance_s": round(F.AUDIO_HOP / F.AUDIO_RATE, 3)}


def current_pairs(session: Session, case_id: uuid.UUID) -> list[MediaRelationship]:
    return list(session.scalars(select(MediaRelationship).where(MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None))))


def latest_summary(session: Session, evidence_id: uuid.UUID) -> dict:
    row = session.scalars(select(EvidenceMetadata).where(EvidenceMetadata.evidence_id == evidence_id, EvidenceMetadata.status == "EXTRACTED")
                          .order_by(EvidenceMetadata.extracted_at.desc()).limit(1)).first()
    return row.summary if row else {}


def video_alignment(fa: dict, fb: dict) -> dict | None:
    hb = np.array([int(f["phash"], 16) for f in fb["frames"]], dtype=np.uint64)
    tb = np.array([f["t"] for f in fb["frames"]])
    pairs = []
    for f in fa["frames"]:
        d = np.bitwise_count(hb ^ np.uint64(int(f["phash"], 16)))
        j = int(np.argmin(d))
        if d[j] <= F.PHASH_MATCH:
            pairs.append((f["t"], tb[j]))
    if len(pairs) < 3:
        return None
    ta_, tb_ = np.array(pairs).T
    speed, offset = np.polyfit(ta_, tb_, 1) if np.ptp(ta_) > 0 else (1.0, float(np.median(tb_ - ta_)))
    residual = float(np.sqrt(np.mean((tb_ - (speed * ta_ + offset)) ** 2)))
    return {"method": "frame pHash matches, least-squares line", "matched_frames": len(pairs), "frames_a": len(fa["frames"]),
            "frames_b": len(fb["frames"]), "speed": round(float(speed), 4), "offset_s": round(float(offset), 3),
            "overlap_a_s": [round(float(ta_.min()), 3), round(float(ta_.max()), 3)], "overlap_b_s": [round(float(tb_.min()), 3), round(float(tb_.max()), 3)],
            "rms_residual_s": round(residual, 3), "tolerance_s": PARAMETERS["video_tolerance_s"]}


def audio_alignment(fa: dict, fb: dict) -> dict | None:
    best = F.audio_match(np.array(fa["values"], dtype=np.uint32), np.array(fb["values"], dtype=np.uint32))
    if best is None:
        return None
    hop = F.AUDIO_HOP / F.AUDIO_RATE
    return {"method": "audio sub-fingerprints, lowest bit error rate", "bit_error_rate": round(best[0], 4), "matched": best[0] <= F.AUDIO_BER_MATCH,
            "offset_s": round(best[1] * hop, 3), "tolerance_s": PARAMETERS["audio_tolerance_s"]}


def build(session: Session, case_id: uuid.UUID) -> tuple[list[Finding], list[uuid.UUID]]:
    prints = case_fingerprints(session, case_id)
    numbers = dict(session.execute(select(Evidence.id, Evidence.evidence_number).where(Evidence.case_id == case_id)).all())
    findings, involved = [], set()
    for rel in current_pairs(session, case_id):
        a, b = rel.evidence_a, rel.evidence_b
        fa, fb = prints.get(a, {}), prints.get(b, {})
        m: dict = {"relationship_id": str(rel.id), "relationship": rel.kind, "evidence_a": str(a), "evidence_b": str(b)}
        if "VIDEO_FRAME_DHASH" in fa and "VIDEO_FRAME_DHASH" in fb:
            m["video"] = video_alignment(fa["VIDEO_FRAME_DHASH"], fb["VIDEO_FRAME_DHASH"])
        if "AUDIO_SUBFINGERPRINT" in fa and "AUDIO_SUBFINGERPRINT" in fb:
            m["audio"] = audio_alignment(fa["AUDIO_SUBFINGERPRINT"], fb["AUDIO_SUBFINGERPRINT"])
        sa, sb = latest_summary(session, a), latest_summary(session, b)
        da = (sa.get("width"), sa.get("height")) if sa.get("width") else next(((v.get("width"), v.get("height")) for v in sa.get("video_streams", [])), (None, None))
        db = (sb.get("width"), sb.get("height")) if sb.get("width") else next(((v.get("width"), v.get("height")) for v in sb.get("video_streams", [])), (None, None))
        if all(da) and all(db):
            m["spatial"] = {"size_a": list(da), "size_b": list(db), "scale_x": round(db[0] / da[0], 4), "scale_y": round(db[1] / da[1], 4)}
        m["duration_a_s"] = (sa.get("container") or {}).get("duration_seconds")
        m["duration_b_s"] = (sb.get("container") or {}).get("duration_seconds")
        if not any(m.get(k) for k in ("video", "audio", "spatial")):
            continue
        involved |= {a, b}
        label = f"EVD-{numbers.get(a, 0):04d} → EVD-{numbers.get(b, 0):04d}"
        parts = []
        if m.get("video"):
            parts.append(f"video offset {m['video']['offset_s']:+.2f} s at speed {m['video']['speed']:.3f}")
        if m.get("audio") and m["audio"]["matched"]:
            parts.append(f"audio offset {m['audio']['offset_s']:+.3f} s")
        if m.get("spatial") and not parts:
            parts.append(f"scale {m['spatial']['scale_x']:.3f} × {m['spatial']['scale_y']:.3f}")
        findings.append(Finding(
            module_id=MODULE, evidence_ids=[a, b], assertion=Assertion.OBSERVATION, finding_type="ALIGNMENT",
            title=f"Aligned {label}: " + ("; ".join(parts) or "no temporal match"),
            description="Where the two versions line up: a time in the first maps to time × speed + offset in the second.",
            measurement=m, score=m["video"]["rms_residual_s"] if m.get("video") else None,
            score_kind=ScoreKind.METHOD_SPECIFIC if m.get("video") else None,
            limitations=["Video alignment uses one frame per second (±0.5 s)", "Static footage aligns poorly: few distinct frames to match"],
            parameters=PARAMETERS))
    return findings, sorted(involved, key=str)
