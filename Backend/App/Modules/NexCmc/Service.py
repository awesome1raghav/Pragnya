"""NEX-CMC Cross-Modal Correlation (archive §4, module 14): where independent signals agree or disagree.

Reads the current findings of IMG, VID, AUD, PRV and TRN in the case (the A1 edges) and states:
  COINCIDENT_DISCONTINUITY   a visual discontinuity (VID) and an audio discontinuity or digital silence (AUD) in the
                             same video within 0.5 s: two independent methods point at the same moment.
  SIGNALS_AGREE              provenance verification failed (PRV) and an image method found a localised
                             inconsistency (IMG) in the same item.
  SIGNALS_DISAGREE           valid content credentials (PRV) alongside a detector score above its threshold, or a
                             transformation hypothesis (TRN) on an item whose credentials are valid.
Agreement raises attention; it does not prove manipulation. Disagreement is reported, never resolved here.
"""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding
from Database.PostgreSQL.Models import AnalysisFinding, AnalysisResult, Evidence

MODULE, VERSION = "NEX-CMC", "nextron-cmc/1"
PARAMETERS = {"coincidence_s": 0.5}
VISUAL = {"VISUAL_DISCONTINUITY", "TIMESTAMP_GAP"}
AUDIBLE = {"SPECTRAL_DISCONTINUITY", "DIGITAL_SILENCE"}
LOCAL_IMAGE = {"NOISE_LEVEL_INCONSISTENCY", "ELA_LOCAL_RESPONSE"}


def build(session: Session, case_id: uuid.UUID) -> tuple[list[Finding], list[uuid.UUID]]:
    numbers = dict(session.execute(select(Evidence.id, Evidence.evidence_number).where(Evidence.case_id == case_id)).all())
    rows = session.execute(
        select(AnalysisFinding).join(AnalysisResult, AnalysisResult.id == AnalysisFinding.result_id)
        .where(AnalysisFinding.case_id == case_id, AnalysisResult.superseded_at.is_(None),
               AnalysisFinding.module_id.in_(("NEX-IMG", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-TRN")))
        .order_by(AnalysisFinding.created_at.desc())).scalars().all()
    by_item: dict[uuid.UUID, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    seen = set()
    for f in rows:
        key = (f.module_id, tuple(f.evidence_ids), f.finding_type, f.title)
        if key in seen:  # several runs of one module: keep each distinct finding once (newest first)
            continue
        seen.add(key)
        for e in f.evidence_ids:
            by_item[e][f.module_id].append(f)

    findings, involved = [], set()

    def add(kind: str, item: uuid.UUID, title: str, text: str, basis: dict, cited: list[AnalysisFinding]) -> None:
        involved.add(item)
        findings.append(Finding(module_id=MODULE, evidence_ids=[item], assertion=Assertion.INFERENCE, finding_type=kind,
                                title=f"EVD-{numbers.get(item, 0):04d}: {title}", description=text,
                                measurement=basis | {"finding_ids": [str(c.id) for c in cited]},
                                limitations=["Correlation of findings, each with its own limitations; agreement is not proof"],
                                parameters=PARAMETERS))

    for item, mods in by_item.items():
        visual = [f for f in mods["NEX-VID"] if f.finding_type in VISUAL and f.payload.get("time_range")]
        audible = [f for f in mods["NEX-AUD"] if f.finding_type in AUDIBLE and f.payload.get("time_range")]
        for v in visual:
            tv = v.payload["time_range"]["end_seconds"]
            near = [a for a in audible if abs(a.payload["time_range"]["start_seconds"] - tv) <= PARAMETERS["coincidence_s"]
                    or abs(a.payload["time_range"]["end_seconds"] - tv) <= PARAMETERS["coincidence_s"]]
            if near:
                ta = near[0].payload["time_range"]["start_seconds"]
                add("COINCIDENT_DISCONTINUITY", item, f"picture and sound both break near {tv:.2f} s",
                    f"{v.finding_type.replace('_', ' ').lower()} at {tv:.2f} s and {near[0].finding_type.replace('_', ' ').lower()} at {ta:.2f} s: "
                    "an edit point is one explanation; a scene change with a sound change is another.",
                    {"visual_s": tv, "audio_s": ta}, [v, near[0]])
        invalid = [f for f in mods["NEX-PRV"] if f.finding_type == "CONTENT_CREDENTIALS_INVALID"]
        valid = [f for f in mods["NEX-PRV"] if f.finding_type == "CONTENT_CREDENTIALS_VALID"]
        local = [f for f in mods["NEX-IMG"] if f.finding_type in LOCAL_IMAGE]
        if invalid and local:
            add("SIGNALS_AGREE", item, "credentials fail and a region looks inconsistent",
                "The content changed after signing (PRV) and an image method localised an inconsistency (IMG).", {}, [invalid[0], local[0]])
        detector = [f for f in mods["NEX-IMG"] + mods["NEX-AUD"] if f.finding_type.startswith("SYNTHETIC_") and f.payload["measurement"].get("above_threshold")]
        edited = mods["NEX-TRN"]
        if valid and (detector or edited):
            other = (detector or edited)[0]
            add("SIGNALS_DISAGREE", item, "valid credentials, yet another method flags it",
                f"Content credentials verify (PRV), while {other.module_id} reports {other.finding_type.replace('_', ' ').lower()}. "
                "Both are reported; neither overrides the other.", {}, [valid[0], other])
    return findings, sorted(involved, key=str)
