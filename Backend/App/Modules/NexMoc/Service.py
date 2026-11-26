"""NEX-MOC Media Lineage: candidate relationships between versions of the same media in a case (archive §4, module 11).

Inputs (A1 edges): NEX-FPM's fingerprints (REQUIRED) and NEX-SRC's source records (OPTIONAL). For every pair of
fingerprinted evidence items whose fingerprints match, MOC records a CANDIDATE relationship with the method,
distances and offset that support it. When sources state publication times for both items, the one stated earlier
is recorded as *earlier observed*, with the times as its basis; NEXTRON never calls an item "the original":
the earliest observed copy is only the earliest NEXTRON has seen. Each run replaces the case's previous candidates
(they are kept, marked superseded), because new evidence or sources can change them.
"""

import itertools
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind
from Backend.App.Modules.NexFpm import Fingerprints as F
from Backend.App.Modules.NexFpm.Service import case_fingerprints
from Database.PostgreSQL.Models import Evidence, MediaRelationship, SourceRecord

MODULE = "NEX-MOC"
VERSION = "nextron-moc/1"
PARAMETERS = {"fingerprints": F.ALGORITHM}


def _when(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build(session: Session, case_id: uuid.UUID, execution_id: uuid.UUID) -> tuple[list[Finding], list[uuid.UUID], dict]:
    prints = case_fingerprints(session, case_id)
    numbers = dict(session.execute(select(Evidence.id, Evidence.evidence_number).where(Evidence.case_id == case_id)).all())
    claimed: dict[uuid.UUID, tuple[datetime, str, str]] = {}
    for s in session.scalars(select(SourceRecord).where(SourceRecord.case_id == case_id, SourceRecord.evidence_id.is_not(None))):
        when = _when(s.claimed_publication_time)
        if when and (s.evidence_id not in claimed or when < claimed[s.evidence_id][0]):
            claimed[s.evidence_id] = (when, s.display_number, s.claimed_publication_time)

    now = datetime.now(timezone.utc)
    session.execute(update(MediaRelationship).where(MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None))
                    .values(superseded_at=now))
    findings, involved, counts = [], set(), {}
    for a, b in itertools.combinations(sorted(prints, key=lambda e: numbers.get(e, 0)), 2):
        matches = F.compare(prints[a], prints[b])
        if not matches:
            continue
        m = matches[0]
        earlier, basis = None, None
        if a in claimed and b in claimed and claimed[a][0] != claimed[b][0]:
            first, second = (a, b) if claimed[a][0] < claimed[b][0] else (b, a)
            earlier = first
            basis = (f"{claimed[first][1]} states publication {claimed[first][2]}; {claimed[second][1]} states {claimed[second][2]} "
                     "(times as claimed by the sources)")
        session.add(MediaRelationship(case_id=case_id, evidence_a=a, evidence_b=b, kind=m.kind, similarity=m.similarity, earlier_observed=earlier,
                                      ordering_basis=basis, basis={"method": F.ALGORITHM, **m.measurement, "other_matches": [x.kind for x in matches[1:]]},
                                      execution_id=execution_id))
        counts[m.kind] = counts.get(m.kind, 0) + 1
        involved |= {a, b}
        label = f"EVD-{numbers.get(a, 0):04d} and EVD-{numbers.get(b, 0):04d}"
        findings.append(Finding(
            module_id=MODULE, evidence_ids=[a, b], assertion=Assertion.INFERENCE, finding_type="LINEAGE_CANDIDATE",
            title=f"{m.kind.replace('_', ' ').capitalize()}: {label}" + (f"; EVD-{numbers.get(earlier, 0):04d} observed earlier" if earlier else ""),
            description=("These items are candidate versions of the same media, from fingerprint similarity. "
                         + (basis + ". " if basis else "No stated publication times order them. ")
                         + "A candidate is not a confirmed derivation; review decides that."),
            measurement={"relationship": m.kind, "similarity": m.similarity, **m.measurement, "earlier_observed": str(earlier) if earlier else None},
            score=m.similarity, score_kind=ScoreKind.SIMILARITY,
            limitations=["Similarity is not proof of common origin or of who copied whom",
                         "Earlier observed means earlier according to the sources' own claims, which can be wrong or edited"],
            parameters=PARAMETERS,
        ))
    session.flush()
    return findings, sorted(involved, key=str), {"pairs_compared": len(prints) * (len(prints) - 1) // 2, "candidates": counts,
                                                  "fingerprinted_evidence": len(prints)}
