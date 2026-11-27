"""Only the newest result per module and scope is current: a later run supersedes the earlier one (once, by trigger),
and the earlier result stays stored. Before migration 0010 every re-run left its predecessors current."""

import pytest
from sqlalchemy import func, select

from Database.PostgreSQL.Models import AnalysisExecution, AnalysisResult
from Tests.Integration.Orchestration.test_sources_lineage import drain
from Tests.Integration.Orchestration.test_tmir import API, api, db, fresh, new_case, upload  # noqa: F401 — fixtures

pytestmark = pytest.mark.postgres


def test_later_case_results_supersede_earlier_ones(api, media):
    case_id = new_case(api)
    first = upload(api, case_id, media["png"], "a.png", "image/png")
    drain(api)
    upload(api, case_id, media["jpeg_exif"], "b.jpg", "image/jpeg")  # changes every case-level module's inputs
    drain(api)
    with db(api) as session:
        def count(module, current):
            q = select(func.count()).select_from(AnalysisResult).join(AnalysisExecution, AnalysisExecution.id == AnalysisResult.execution_id) \
                .where(AnalysisResult.module_id == module, AnalysisExecution.scope_ref == case_id)
            return session.scalar(q.where(AnalysisResult.superseded_at.is_(None)) if current else q)
        for module in ("NEX-EGC", "NEX-REC", "NEX-CMC"):
            assert count(module, True) == 1 and count(module, False) == 2, module  # one current, the earlier one kept
    findings = api.get(f"{API}/evidence/{first['evidence_id']}/analysis").json()["data"]["findings"]
    keys = [(f["module_id"], f["finding_type"], f["title"]) for f in findings]
    assert len(keys) == len(set(keys))  # nothing listed twice
