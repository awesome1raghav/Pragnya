"""NEX-TRN Transformation Analysis (archive §4, module 13): what was done to get from one version to the other.

Reads NEX-ALN's alignment of each pair (its result, passed by T-MIR) and both items' metadata, and states each
transformation it can support as a HYPOTHESIS (INFERENCE) with the measurements behind it. Direction is not
asserted: "b is a trimmed version of a" also fits "a was extended"; the earlier-observed item (NEX-MOC) is quoted
when known.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding
from Backend.App.Modules.NexAln.Service import latest_summary
from Database.PostgreSQL.Models import AnalysisFinding, Evidence

MODULE, VERSION = "NEX-TRN", "nextron-trn/1"
PARAMETERS = {"speed_tolerance": 0.03, "trim_tolerance_s": 0.75, "scale_tolerance": 0.02, "audio_replaced_ber": 0.40}


def _codec(summary: dict) -> tuple:
    v = (summary.get("video_streams") or [{}])[0]
    a = (summary.get("audio_streams") or [{}])[0]
    return ((summary.get("container") or {}).get("format_name") or summary.get("format"), v.get("codec"), a.get("codec"))


def hypotheses(m: dict, sa: dict, sb: dict) -> list[tuple[str, str, dict]]:
    out = []
    video, audio, spatial = m.get("video"), m.get("audio"), m.get("spatial")
    if video:
        if abs(video["speed"] - 1) > PARAMETERS["speed_tolerance"]:
            out.append(("SPEED_CHANGED", f"Playback speed differs by a factor of {video['speed']:.3f}", {"speed": video["speed"]}))
        for side, span, duration in (("a", video["overlap_a_s"], m.get("duration_a_s")), ("b", video["overlap_b_s"], m.get("duration_b_s"))):
            if duration and (span[0] > PARAMETERS["trim_tolerance_s"] or duration - span[1] > PARAMETERS["trim_tolerance_s"] + 1):
                other = "b" if side == "a" else "a"
                out.append(("TRIMMED", f"Only {span[0]:.1f}–{span[1]:.1f} s of {side} ({duration:.1f} s) appears in {other}: {other} looks like a trimmed copy",
                            {"side_with_extra": side, "shared_span_s": span, "duration_s": duration}))
    if video and audio is not None and not audio["matched"] and audio["bit_error_rate"] >= PARAMETERS["audio_replaced_ber"] \
            and video["matched_frames"] >= max(3, 0.5 * min(video["frames_a"], video["frames_b"])):
        out.append(("AUDIO_REPLACED", "The pictures match but the sound does not: the audio track differs between the versions",
                    {"video_matched_frames": video["matched_frames"], "audio_bit_error_rate": audio["bit_error_rate"]}))
    if spatial:
        sx, sy = spatial["scale_x"], spatial["scale_y"]
        if abs(sx - sy) > PARAMETERS["scale_tolerance"]:
            out.append(("CROPPED_OR_REFRAMED", f"The aspect ratio changed ({spatial['size_a']} → {spatial['size_b']})", spatial))
        elif abs(sx - 1) > PARAMETERS["scale_tolerance"]:
            out.append(("RESIZED", f"Resized by {sx:.3f} ({spatial['size_a']} → {spatial['size_b']})", spatial))
    ca, cb = _codec(sa), _codec(sb)
    if any(ca) and any(cb) and ca != cb:
        out.append(("RE_ENCODED", f"Container or codecs differ ({'/'.join(map(str, ca))} → {'/'.join(map(str, cb))})", {"a": list(ca), "b": list(cb)}))
    return out


def build(session: Session, case_id: uuid.UUID, alignment_result_ids: list[uuid.UUID]) -> tuple[list[Finding], list[uuid.UUID]]:
    numbers = dict(session.execute(select(Evidence.id, Evidence.evidence_number).where(Evidence.case_id == case_id)).all())
    rows = session.scalars(select(AnalysisFinding).where(AnalysisFinding.result_id.in_(alignment_result_ids),
                                                          AnalysisFinding.finding_type == "ALIGNMENT")).all() if alignment_result_ids else []
    findings, involved = [], set()
    for row in rows:
        m = row.payload["measurement"]
        a, b = uuid.UUID(m["evidence_a"]), uuid.UUID(m["evidence_b"])
        for kind, text, basis in hypotheses(m, latest_summary(session, a), latest_summary(session, b)):
            involved |= {a, b}
            findings.append(Finding(
                module_id=MODULE, evidence_ids=[a, b], assertion=Assertion.INFERENCE, finding_type=kind,
                title=f"{kind.replace('_', ' ').capitalize()}: EVD-{numbers.get(a, 0):04d} / EVD-{numbers.get(b, 0):04d}",
                description=text + ". A hypothesis from measured alignment and metadata, not an observed edit.",
                measurement={"alignment_finding_id": str(row.id), **basis},
                limitations=["Direction is not established: either version could be the edited one",
                             "Hypotheses rest on one-frame-per-second alignment and container metadata"],
                parameters=PARAMETERS))
    return findings, sorted(involved, key=str)
