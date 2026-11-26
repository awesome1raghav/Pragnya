"""The Neo4j projection against the local Neo4j (skipped when it is not reachable).

Checks: the worker's idle tick projects a case's latest graph snapshot; running it again changes nothing; a new
snapshot replaces the subgraph; the checkpoint and lag are reported; rebuild re-projects from PostgreSQL.
"""

import pytest

from Backend.App.Config import get_settings
from Tests.Integration.Orchestration.test_sources_lineage import drain
from Tests.Integration.Orchestration.test_tmir import API, api, fresh, new_case, upload  # noqa: F401 — fixtures
from Tests.conftest import build_app

pytestmark = pytest.mark.postgres
SETTINGS = get_settings()


def _reachable() -> bool:
    if not SETTINGS.NEO4J_URI:
        return False
    try:
        from neo4j import GraphDatabase

        with GraphDatabase.driver(SETTINGS.NEO4J_URI, auth=(SETTINGS.NEO4J_USER, SETTINGS.NEO4J_PASSWORD.get_secret_value()), connection_timeout=3) as d:
            d.verify_connectivity()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture()
def graph_api(fresh):
    if not _reachable():
        pytest.skip("Neo4j is not reachable at NEO4J_URI")
    from fastapi.testclient import TestClient

    with TestClient(build_app(fresh[0], fresh[1], JOB_RETRY_BASE_SECONDS=0, NEO4J_URI=SETTINGS.NEO4J_URI)) as client:
        yield client


def _counts(client, case_id):
    records, _, _ = client.app.state.graph.driver().execute_query(
        "MATCH (n:NexNode {case_id: $c}) OPTIONAL MATCH (n)-[r]->() RETURN count(DISTINCT n) AS n, count(r) AS r, collect(DISTINCT n.snapshot_id) AS s",
        c=case_id)
    return records[0]["n"], records[0]["r"], records[0]["s"]


def test_projection_follows_snapshots_and_rebuilds(graph_api, media):
    case_id = new_case(graph_api)
    try:
        upload(graph_api, case_id, media["jpeg_exif"], "camera.jpg", "image/jpeg")
        drain(graph_api)
        status = graph_api.get(f"{API}/system/projections").json()["data"][0]
        assert status["reachable"] is True and status["snapshots_pending"] is True and status["lag_events"] > 0
        graph = graph_api.app.state.graph
        assert graph.tick() == 1
        snap = graph_api.get(f"{API}/cases/{case_id}/graph").json()["data"]
        n, r, s = _counts(graph_api, case_id)
        assert (n, r, s) == (snap["counts"]["nodes"], snap["counts"]["edges"], [snap["snapshot_id"]])
        assert graph.tick() == 0 and _counts(graph_api, case_id) == (n, r, s)  # idempotent; nothing new
        assert graph_api.get(f"{API}/system/projections").json()["data"][0]["snapshots_pending"] is False

        upload(graph_api, case_id, media["png"], "second.png", "image/png")
        drain(graph_api)
        graph.tick()
        newer = graph_api.get(f"{API}/cases/{case_id}/graph").json()["data"]
        assert _counts(graph_api, case_id) == (newer["counts"]["nodes"], newer["counts"]["edges"], [newer["snapshot_id"]])

        rebuilt = graph_api.post(f"{API}/system/projections/neo4j/rebuild").json()["data"]
        assert rebuilt["cases_projected"] == 1 and _counts(graph_api, case_id)[2] == [newer["snapshot_id"]]
        assert graph_api.get(f"{API}/system/projections").json()["data"][0]["lag_events"] == 0
    finally:
        graph_api.app.state.graph.project_case(case_id, None)  # leave the shared local graph as it was


def test_projection_disabled_is_reported(api):
    status = api.get(f"{API}/system/projections").json()["data"][0]
    assert (status["configured"], status["reachable"]) == (False, None) and "NEO4J_URI" in status["error"]
    assert api.post(f"{API}/system/projections/neo4j/rebuild").json()["error"]["code"] == "PROJECTION_UNAVAILABLE"
