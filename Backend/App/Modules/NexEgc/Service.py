"""NEX-EGC Evidence Graph Construction (archive §4, module 15): the case as a graph built from stored records only.

Nodes: the case, its evidence, its sources, and the current findings that say something about evidence (feature-only
findings such as hashes and metadata records are left out). Edges: source -RETRIEVED_AS-> evidence;
evidence -CANDIDATE_VERSION- evidence (NEX-MOC, with similarity and "earlier observed"); finding -ABOUT-> evidence;
correlation -CITES-> finding (NEX-CMC). Every edge names the record that supports it, so the graph can be traced
back to PostgreSQL; each build is stored whole as a snapshot (Neo4j holds a projection of the latest one).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Findings import Assertion, Finding
from Backend.App.Realtime import Outbox
from Database.PostgreSQL.Models import AnalysisFinding, AnalysisResult, Case, Evidence, GraphSnapshot, MediaRelationship, SourceRecord

MODULE, VERSION = "NEX-EGC", "nextron-egc/1"
PARAMETERS: dict = {}
FEATURE_ONLY = {"PERCEPTUAL_HASHES", "FINGERPRINTS_RECORDED", "METADATA_RECORDED", "AUDIO_LEVELS", "FRAME_TIMING", "VISUAL_CONTINUITY",
                "SPECTRAL_CONTINUITY", "EFFECTIVE_BANDWIDTH", "ACOUSTIC_FINGERPRINT", "ALIGNMENT"}


def snapshot(session: Session, case_id: uuid.UUID) -> tuple[list[dict], list[dict]]:
    case = session.get(Case, case_id)
    nodes = [{"id": str(case.id), "type": "CASE", "label": case.display_number, "title": case.title}]
    edges: list[dict] = []
    evidence = session.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.evidence_number)).all()
    for e in evidence:
        nodes.append({"id": str(e.id), "type": "EVIDENCE", "label": e.display_number, "media_type": e.media_type, "sha256": e.sha256,
                      "filename": e.original_filename, "received_at": e.received_at.isoformat()})
        edges.append({"from": str(case.id), "to": str(e.id), "type": "CONTAINS", "record": f"evidence:{e.id}"})
    for s in session.scalars(select(SourceRecord).where(SourceRecord.case_id == case_id)):
        nodes.append({"id": str(s.id), "type": "SOURCE", "label": s.display_number, "url": s.normalized_url, "state": s.state,
                      "claimed_publication_time": s.claimed_publication_time})
        if s.evidence_id:
            edges.append({"from": str(s.id), "to": str(s.evidence_id), "type": "RETRIEVED_AS", "record": f"source_records:{s.id}"})
    for r in session.scalars(select(MediaRelationship).where(MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None))):
        edges.append({"from": str(r.evidence_a), "to": str(r.evidence_b), "type": "CANDIDATE_VERSION", "kind": r.kind, "similarity": r.similarity,
                      "earlier_observed": str(r.earlier_observed) if r.earlier_observed else None, "status": r.status,
                      "record": f"media_relationships:{r.id}"})
    findings = session.scalars(select(AnalysisFinding).join(AnalysisResult, AnalysisResult.id == AnalysisFinding.result_id)
                               .where(AnalysisFinding.case_id == case_id, AnalysisResult.superseded_at.is_(None),
                                      AnalysisFinding.module_id != MODULE, AnalysisFinding.module_id != "NEX-REC")
                               .order_by(AnalysisFinding.created_at.desc())).all()
    seen, kept = set(), {}
    for f in findings:
        key = (f.module_id, f.finding_type, tuple(f.evidence_ids), f.title)
        if f.finding_type in FEATURE_ONLY or key in seen:
            continue
        seen.add(key)
        kept[str(f.id)] = f
        nodes.append({"id": str(f.id), "type": "FINDING", "label": f.finding_type, "module": f.module_id, "assertion": f.assertion, "title": f.title})
        for e in f.evidence_ids:
            edges.append({"from": str(f.id), "to": str(e), "type": "ABOUT", "record": f"analysis_findings:{f.id}"})
    for fid, f in kept.items():
        for cited in (f.payload.get("measurement") or {}).get("finding_ids", []):
            if cited in kept:
                edges.append({"from": fid, "to": cited, "type": "CITES", "record": f"analysis_findings:{fid}"})
    return nodes, edges


def build(session: Session, case_id: uuid.UUID, execution_id: uuid.UUID) -> tuple[list[Finding], list[uuid.UUID]]:
    nodes, edges = snapshot(session, case_id)
    counts = {"nodes": len(nodes), "edges": len(edges), **{f"nodes_{t.lower()}": sum(n["type"] == t for n in nodes) for t in ("EVIDENCE", "SOURCE", "FINDING")},
              **{f"edges_{t.lower()}": sum(e["type"] == t for e in edges) for t in ("RETRIEVED_AS", "CANDIDATE_VERSION", "ABOUT", "CITES")}}
    snap = GraphSnapshot(case_id=case_id, execution_id=execution_id, nodes=nodes, edges=edges, counts=counts)
    session.add(snap)
    session.flush()
    Outbox.publish(session, "graph.snapshot_created", aggregate_type="graph", aggregate_id=snap.id, case_id=case_id, payload={"counts": counts})
    evidence_ids = [uuid.UUID(n["id"]) for n in nodes if n["type"] == "EVIDENCE"]
    if not evidence_ids:
        return [], []
    return [Finding(module_id=MODULE, evidence_ids=evidence_ids, assertion=Assertion.OBSERVATION, finding_type="EVIDENCE_GRAPH",
                    title=f"Evidence graph: {counts['nodes']} nodes, {counts['edges']} edges",
                    description="Built from stored records only; every edge names the record that supports it.",
                    measurement={"snapshot_id": str(snap.id), **counts},
                    limitations=["Candidate relationships and hypotheses are drawn as such; the graph shows what is recorded, not what is true"])], evidence_ids
