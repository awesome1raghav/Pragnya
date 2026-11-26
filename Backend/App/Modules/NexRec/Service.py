"""NEX-REC Timeline & Reconstruction (archive §4, module 16): what is known about when, and how sure that is.

Orders the case's dated statements, each labelled by who makes it:
  CLAIMED_CREATION     a timestamp inside the file (EXIF DateTimeOriginal, container creation_time): claimed by the file
  CLAIMED_PUBLICATION  a publication time stated by a source page: claimed by the source
  RECEIVED             when NEXTRON received the evidence: measured by NEXTRON
  RETRIEVED            when NEXTRON retrieved a source: measured by NEXTRON
and reports TIME_CONFLICT where the claims contradict each other (a file claims creation after the source it came
from says it was published; a version observed earlier claims a later creation time). Requires NEX-EGC (A1).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding
from Database.PostgreSQL.Models import Evidence, EvidenceMetadata, MediaRelationship, SourceRecord

MODULE, VERSION = "NEX-REC", "nextron-rec/1"
PARAMETERS = {"conflict_margin_s": 60}


def _parse(text) -> datetime | None:
    if not text or not isinstance(text, str):
        return None
    t = text.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y:%m:%d %H:%M:%S"):
        try:
            value = datetime.fromisoformat(t) if fmt is None else datetime.strptime(t[:19], fmt)
        except ValueError:
            continue
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def build(session: Session, case_id: uuid.UUID) -> tuple[list[Finding], list[uuid.UUID]]:
    evidence = {e.id: e for e in session.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    if not evidence:
        return [], []
    entries: list[dict] = []
    created: dict[uuid.UUID, datetime] = {}
    for e in evidence.values():
        entries.append({"time": e.received_at.isoformat(), "kind": "RECEIVED", "evidence_id": str(e.id), "label": e.display_number, "by": "NEXTRON (measured)"})
        md = session.scalars(select(EvidenceMetadata).where(EvidenceMetadata.evidence_id == e.id, EvidenceMetadata.status == "EXTRACTED")
                             .order_by(EvidenceMetadata.extracted_at.desc()).limit(1)).first()
        for name, value in ((md.summary.get("embedded_timestamps") or {}).items() if md else []):
            when = _parse(value)
            if when:
                created[e.id] = min(created.get(e.id, when), when)
                entries.append({"time": when.isoformat(), "kind": "CLAIMED_CREATION", "evidence_id": str(e.id), "label": f"{e.display_number} {name}",
                                "by": "the file (unverified)", "raw": value})
    published: dict[uuid.UUID, tuple[datetime, str]] = {}
    for s in session.scalars(select(SourceRecord).where(SourceRecord.case_id == case_id)):
        if s.last_retrieved_at:
            entries.append({"time": s.last_retrieved_at.isoformat(), "kind": "RETRIEVED", "source_id": str(s.id), "label": s.display_number, "by": "NEXTRON (measured)"})
        when = _parse(s.claimed_publication_time)
        if when:
            entries.append({"time": when.isoformat(), "kind": "CLAIMED_PUBLICATION", "source_id": str(s.id), "evidence_id": str(s.evidence_id) if s.evidence_id else None,
                            "label": s.display_number, "by": "the source (unverified)", "raw": s.claimed_publication_time})
            if s.evidence_id:
                published[s.evidence_id] = (when, s.display_number)
    entries.sort(key=lambda x: x["time"])

    numbers = {k: v.display_number for k, v in evidence.items()}
    margin = PARAMETERS["conflict_margin_s"]
    findings = [Finding(module_id=MODULE, evidence_ids=list(evidence), assertion=Assertion.OBSERVATION, finding_type="RECONSTRUCTION",
                        title=f"Timeline of {len(entries)} dated statements", measurement={"timeline": entries},
                        description="Dated statements in order. Claimed times are the file's or the source's own claims; only NEXTRON's times are measured.",
                        limitations=["Embedded and published times can be missing, wrong or edited", "Times without a zone are read as UTC"],
                        parameters=PARAMETERS)]
    for e, (pub, src) in published.items():
        if e in created and (created[e] - pub).total_seconds() > margin:
            findings.append(Finding(module_id=MODULE, evidence_ids=[e], assertion=Assertion.INFERENCE, finding_type="TIME_CONFLICT",
                                    title=f"{numbers[e]} claims creation after {src} says it was published",
                                    description=f"The file claims {created[e].isoformat()}; {src} claims publication at {pub.isoformat()}. At least one claim is wrong.",
                                    measurement={"claimed_creation": created[e].isoformat(), "claimed_publication": pub.isoformat(), "source": src},
                                    limitations=["Either claim may be wrong; clocks and time zones are common causes"], parameters=PARAMETERS))
    for r in session.scalars(select(MediaRelationship).where(MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None),
                                                              MediaRelationship.earlier_observed.is_not(None))):
        later = r.evidence_b if r.earlier_observed == r.evidence_a else r.evidence_a
        if r.earlier_observed in created and later in created and (created[r.earlier_observed] - created[later]).total_seconds() > margin:
            findings.append(Finding(module_id=MODULE, evidence_ids=[r.earlier_observed, later], assertion=Assertion.INFERENCE, finding_type="TIME_CONFLICT",
                                    title=f"{numbers[r.earlier_observed]} was observed earlier but claims a later creation than {numbers[later]}",
                                    description="Publication order and embedded creation times disagree.",
                                    measurement={"relationship_id": str(r.id)}, limitations=["Either kind of claim may be wrong"], parameters=PARAMETERS))
    return findings, list(evidence)
