"""NEX-RPT Reporting (archive §4, module 18): versioned reports generated from stored records by a background job.

Requesting a report adds a `reports` row (version n+1 for the case) and queues a REPORT_GENERATION job. The worker
gathers the case as stored: evidence and hashes, sources, each module's current result and findings, the latest
graph snapshot, the reconstruction, and the current reviews. It writes a JSON document and a PDF rendering of it,
both write-once under Reports/<case>/<report>.{json,pdf}, and records their SHA-256. A DRAFT can be requested at
any time; a FINAL needs a current case-conclusion review (edge NEX-INV -> NEX-RPT). Reports quote findings with
their assertion level and limitations, and never upgrade a candidate or inference into a conclusion.
"""

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Contracts.ExecutionStates import JobState, JobType
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexInv import Service as ReviewService
from Backend.App.Realtime import Outbox
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import (AnalysisFinding, AnalysisResult, BacktrackingComparison, Case, Evidence, GraphSnapshot, MediaRelationship, Report,
                                        SourceObservation, SourceRecord)

FORMAT = "nextron-report/1"


def get_report(session: Session, report_id: uuid.UUID) -> Report:
    report = session.get(Report, report_id)
    if report is None:
        raise NextronError(404, ErrorCode.REPORT_NOT_FOUND, "The requested report does not exist")
    return report


def request(session: Session, case_id: uuid.UUID, kind: str, actor: str, settings: Settings) -> tuple[Report, object]:
    Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))
    if kind == "FINAL" and ReviewService.current_conclusion(session, case_id) is None:
        raise NextronError(409, ErrorCode.CONCLUSION_REQUIRED, "A FINAL report needs a reviewed case conclusion; request a DRAFT instead")
    version = (session.scalar(select(func.max(Report.version)).where(Report.case_id == case_id)) or 0) + 1
    report = Report(case_id=case_id, version=version, kind=kind, state="QUEUED", requested_by=actor, summary={})
    session.add(report)
    session.flush()
    job = JobService.enqueue(session, job_type=JobType.REPORT_GENERATION, case_id=case_id, requested_by=actor, settings=settings,
                                parameters={"report_id": str(report.id)})
    report.job_id = job.id
    Outbox.publish(session, "report.queued", aggregate_type="report", aggregate_id=report.id, case_id=case_id,
                   payload={"report_number": report.display_number, "version": version, "kind": kind, "job_id": str(job.id)})
    session.commit()
    return report, job


def list_reports(session: Session, case_id: uuid.UUID) -> list[Report]:
    return list(session.scalars(select(Report).where(Report.case_id == case_id).order_by(Report.version.desc())))


def _review(r) -> dict:
    return {"review": r.display_number, "subject_type": r.subject_type, "subject_id": str(r.subject_id), "version": r.version,
            "decision": r.decision, "rationale": r.rationale, "reviewer": r.reviewer, "at": r.created_at.isoformat(),
            "reconstruction_result_id": str(r.reconstruction_result_id) if r.reconstruction_result_id else None}


def gather(session: Session, report: Report) -> dict:
    """The report document: everything is read from stored records; nothing is recomputed here."""
    case = session.get(Case, report.case_id)
    evidence = session.scalars(select(Evidence).where(Evidence.case_id == case.id).order_by(Evidence.evidence_number)).all()
    numbers = {e.id: e.display_number for e in evidence}
    results = session.scalars(select(AnalysisResult).where(AnalysisResult.case_id == case.id, AnalysisResult.superseded_at.is_(None))
                              .order_by(AnalysisResult.module_id, AnalysisResult.created_at)).all()
    findings = session.scalars(select(AnalysisFinding).where(AnalysisFinding.result_id.in_([r.id for r in results]))
                               .order_by(AnalysisFinding.module_id, AnalysisFinding.created_at)).all() if results else []
    by_result: dict[uuid.UUID, list] = {}
    for f in findings:
        p = f.payload or {}
        by_result.setdefault(f.result_id, []).append({
            "finding_id": str(f.id), "type": f.finding_type, "assertion": f.assertion, "title": f.title, "description": f.description,
            "evidence": [numbers.get(e, str(e)) for e in f.evidence_ids], "score": f.score, "score_kind": f.score_kind,
            "limitations": p.get("limitations", []), "threshold": p.get("threshold")})
    modules = [{"module": r.module_id, "status": r.status, "evidence": [numbers.get(uuid.UUID(e), e) for e in (r.envelope.get("evidence_ids") or [])],
                "result_id": str(r.id), "produced_at": r.created_at.isoformat(), "findings": by_result.get(r.id, [])} for r in results]
    graph = session.scalars(select(GraphSnapshot).where(GraphSnapshot.case_id == case.id).order_by(GraphSnapshot.created_at.desc()).limit(1)).first()
    rec = ReviewService.current_reconstruction(session, case.id)
    row = session.scalars(select(AnalysisFinding).where(AnalysisFinding.result_id == rec.id, AnalysisFinding.finding_type == "RECONSTRUCTION")).first() if rec else None
    timeline = (row.payload.get("measurement") or {}).get("timeline", []) if row else []
    relationships = session.scalars(select(MediaRelationship).where(MediaRelationship.case_id == case.id, MediaRelationship.superseded_at.is_(None))).all()
    sources = session.scalars(select(SourceRecord).where(SourceRecord.case_id == case.id).order_by(SourceRecord.source_number)).all()
    source_ids = {s.id: s.display_number for s in sources}
    occurrences = session.scalars(select(SourceObservation).where(SourceObservation.source_id.in_(source_ids))
                                  .order_by(SourceObservation.source_id, SourceObservation.revision)).all() if source_ids else []
    comparisons = session.scalars(select(BacktrackingComparison).where(BacktrackingComparison.case_id == case.id)
                                  .order_by(BacktrackingComparison.created_at)).all()
    current_reviews = ReviewService.list_reviews(session, case.id, current_only=True)
    comparison_reviews = {r.subject_id: r for r in current_reviews if r.subject_type == "BACKTRACK_COMPARISON"}
    conclusion = ReviewService.current_conclusion(session, case.id)
    return {
        "format": FORMAT, "report": report.display_number, "version": report.version, "kind": report.kind,
        "case": {"case": case.display_number, "title": case.title, "status": case.status, "description": case.description},
        "generated_by": report.requested_by,
        "evidence": [{"evidence": e.display_number, "filename": e.original_filename, "media_type": e.media_type, "mime_type": e.mime_type,
                      "size_bytes": e.size_bytes, "sha256": e.sha256, "source_type": e.source_type, "received_at": e.received_at.isoformat()}
                     for e in evidence],
        "sources": [{"source": s.display_number, "url": s.normalized_url, "state": s.state, "title": s.title,
                     "claimed_publication_time": s.claimed_publication_time, "evidence": numbers.get(s.evidence_id)} for s in sources],
        "source_occurrences": [{"source": source_ids[o.source_id], "revision": o.revision,
                                "outcome": o.outcome, "evidence": numbers.get(o.evidence_id),
                                "observed_at": o.retrieved_at.isoformat()} for o in occurrences],
        "modules": modules,
        "lineage": [{"a": numbers.get(r.evidence_a), "b": numbers.get(r.evidence_b), "kind": r.kind, "status": r.status,
                     "similarity": r.similarity, "earlier_observed": numbers.get(r.earlier_observed)} for r in relationships],
        "backtracking": [{"comparison_id": str(r.id), "seed": numbers.get(r.seed_evidence_id),
                          "candidate": numbers.get(r.candidate_evidence_id), "seed_sha256": r.seed_sha256,
                          "candidate_sha256": r.candidate_sha256, "algorithm": r.algorithm,
                          "fingerprint_algorithm": r.fingerprint_algorithm, "status": r.status,
                          "coverage_seed_percent": r.result.get("submitted_coverage_percent"),
                          "coverage_candidate_percent": r.result.get("candidate_coverage_percent"),
                          "review": _review(comparison_reviews[r.id]) if r.id in comparison_reviews else None}
                         for r in comparisons],
        "graph": {"snapshot_id": str(graph.id), "counts": graph.counts, "built_at": graph.created_at.isoformat()} if graph else None,
        "timeline": timeline,
        "reviews": [_review(r) for r in current_reviews],
        "conclusion": _review(conclusion) if conclusion else None,
        "statement": ("Findings are reported at their assertion level: OBSERVATION (measured), INFERENCE (a method's reading with its stated "
                      "threshold and limitations), CANDIDATE (proposed, not established). Investigator decisions are listed separately "
                      "and do not alter findings."),
    }


def render_pdf(doc: dict) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    out = io.BytesIO()
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{doc['report']} {doc['case']['case']}", author="NEXTRON", creator="NEXTRON", invariant=1)
    p = lambda text, style="BodyText": Paragraph(escape(str(text)), styles[style])  # noqa: E731
    small = styles["BodyText"].clone("small", fontSize=7.5, leading=9.5)

    def table(rows, widths):
        t = Table([[Paragraph(escape(str(c if c is not None else "—")), small) for c in r] for r in rows], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, "#999999"), ("BACKGROUND", (0, 0), (-1, 0), "#e8e8e8"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    story = [p(f"NEXTRON report {doc['report']} (v{doc['version']}, {doc['kind']})", "Title"),
             p(f"{doc['case']['case']}: {doc['case']['title']} — status {doc['case']['status']}"), p(doc["statement"]), Spacer(1, 4 * mm),
             p("Evidence", "Heading2"),
             table([["Evidence", "File", "Type", "Bytes", "SHA-256", "Received"]] +
                   [[e["evidence"], e["filename"], e["media_type"], e["size_bytes"], e["sha256"], e["received_at"]] for e in doc["evidence"]],
                   [18 * mm, 32 * mm, 14 * mm, 16 * mm, 60 * mm, 38 * mm])]
    if doc["sources"]:
        story += [p("Sources", "Heading2"), table([["Source", "URL", "State", "Claimed publication", "Evidence"]] +
                                                  [[s["source"], s["url"], s["state"], s["claimed_publication_time"], s["evidence"]] for s in doc["sources"]],
                                                  [18 * mm, 80 * mm, 26 * mm, 36 * mm, 18 * mm])]
    if doc["conclusion"]:
        c = doc["conclusion"]
        story += [p("Case conclusion (investigator decision)", "Heading2"), p(f"{c['decision']} — {c['rationale']} ({c['reviewer']}, {c['at']}, v{c['version']})")]
    story.append(p("Module results", "Heading2"))
    for m in doc["modules"]:
        story.append(p(f"{m['module']} — {m['status']} ({', '.join(m['evidence']) or 'case'})", "Heading4"))
        for f in m["findings"]:
            line = f"[{f['assertion']}] {f['title']}"
            if f["score"] is not None:
                line += f" (score {f['score']:.4g}, {f['score_kind']})"
            story.append(p(line))
            if f["limitations"]:
                story.append(Paragraph(escape("Limitations: " + "; ".join(map(str, f["limitations"]))), small))
    if doc["lineage"]:
        story += [p("Candidate version relationships", "Heading2"), table([["A", "B", "Kind", "Status", "Similarity", "Earlier observed"]] +
                  [[r["a"], r["b"], r["kind"], r["status"], f"{r['similarity']:.3f}", r["earlier_observed"]] for r in doc["lineage"]],
                  [20 * mm, 20 * mm, 30 * mm, 26 * mm, 24 * mm, 30 * mm])]
    if doc["backtracking"]:
        story += [p("Local backtracking comparisons", "Heading2"),
                  table([["Comparison", "Seed", "Candidate", "Status", "Coverage seed", "Review"]] +
                        [[r["comparison_id"], r["seed"], r["candidate"], r["status"],
                          r["coverage_seed_percent"], r["review"]["decision"] if r["review"] else "Unreviewed"]
                         for r in doc["backtracking"]], [38 * mm, 22 * mm, 22 * mm, 37 * mm, 29 * mm, 30 * mm])]
    if doc["timeline"]:
        story += [p("Timeline (claimed and measured times)", "Heading2"), table([["Time", "Kind", "Item", "Stated by"]] +
                  [[t["time"], t["kind"], t["label"], t["by"]] for t in doc["timeline"]], [44 * mm, 34 * mm, 60 * mm, 40 * mm])]
    if doc["reviews"]:
        story += [p("Investigator reviews (current versions)", "Heading2"), table([["Review", "Subject", "Decision", "Rationale", "By"]] +
                  [[r["review"], f"{r['subject_type']} v{r['version']}", r["decision"], r["rationale"], r["reviewer"]] for r in doc["reviews"]],
                  [18 * mm, 34 * mm, 30 * mm, 76 * mm, 20 * mm])]
    pdf.build(story)
    return out.getvalue()


def generate(factory: sessionmaker[Session], storage: LocalStorage, settings: Settings, job_id: uuid.UUID, worker_id: str) -> JobState | None:
    with factory() as session:
        job = JobService.get_job(session, job_id)
        report = get_report(session, uuid.UUID(job.parameters["report_id"]))
        report_id, case_id = report.id, report.case_id
        try:
            doc = gather(session, report)
            data = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
            pdf = render_pdf(doc)
            error = None
        except Exception as exc:  # noqa: BLE001 — recorded on the report and the job
            error = f"{type(exc).__name__}: {exc}"[:500]
        session.rollback()
    keys = {"json": f"Reports/{case_id}/{report_id}.json", "pdf": f"Reports/{case_id}/{report_id}.pdf"}
    if error is None:
        try:
            storage.write_report(keys["json"], data)
            storage.write_report(keys["pdf"], pdf)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"[:500]
    with factory() as session:
        if not JobService.fence(session, job_id, worker_id):
            session.rollback()
            return None
        report = session.get(Report, report_id, with_for_update=True)
        if error is None:
            report.state, report.json_key, report.pdf_key = "GENERATED", keys["json"], keys["pdf"]
            report.json_sha256, report.pdf_sha256 = hashlib.sha256(data).hexdigest(), hashlib.sha256(pdf).hexdigest()
            report.summary = {"evidence": len(doc["evidence"]), "sources": len(doc["sources"]), "modules": len(doc["modules"]),
                              "findings": sum(len(m["findings"]) for m in doc["modules"]), "reviews": len(doc["reviews"]),
                              "backtracking_comparisons": len(doc["backtracking"]),
                              "conclusion": doc["conclusion"]["decision"] if doc["conclusion"] else None}
        else:
            report.state, report.error = "FAILED", error
        report.generated_at = datetime.now(timezone.utc)
        Outbox.publish(session, "report.generated" if error is None else "report.failed", aggregate_type="report", aggregate_id=report.id,
                       case_id=case_id, payload={"report_number": report.display_number, "version": report.version, "kind": report.kind,
                                                 "json_sha256": report.json_sha256, "pdf_sha256": report.pdf_sha256, "error": error})
        session.commit()
        job = JobService.get_job(session, job_id)
        state = JobState.COMPLETED if error is None else JobState.FAILED
        if not JobService.finish(session, job, worker_id, state, progress={"planned": 1, "finished": 1, "by_state": {state.value: 1}, "current": None},
                                 error={"code": "REPORT_FAILED", "message": error} if error else None):
            return None
        return state
