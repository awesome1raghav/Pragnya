"""The module catalogue must match the canonical module connectivity flowchart (A1) exactly."""

from fastapi.testclient import TestClient

from Backend.App.Orchestration import ModuleCatalog

# Transcribed independently from Flowchart A1's solid arrows.
A1_EDGES = {
    ("NEX-CM", "NEX-CAP"), ("NEX-CAP", "NEX-EVD"),
    ("NEX-EVD", "NEX-MET"), ("NEX-EVD", "NEX-IMG"), ("NEX-EVD", "NEX-VID"), ("NEX-EVD", "NEX-AUD"), ("NEX-EVD", "NEX-PRV"),
    ("NEX-MET", "NEX-FPM"), ("NEX-IMG", "NEX-FPM"), ("NEX-VID", "NEX-FPM"), ("NEX-AUD", "NEX-FPM"), ("NEX-SRC", "NEX-FPM"),
    ("NEX-FPM", "NEX-MOC"), ("NEX-SRC", "NEX-MOC"),
    ("NEX-MOC", "NEX-ALN"), ("NEX-IMG", "NEX-ALN"), ("NEX-VID", "NEX-ALN"),
    ("NEX-ALN", "NEX-TRN"), ("NEX-MOC", "NEX-TRN"),
    ("NEX-IMG", "NEX-CMC"), ("NEX-VID", "NEX-CMC"), ("NEX-AUD", "NEX-CMC"), ("NEX-PRV", "NEX-CMC"), ("NEX-TRN", "NEX-CMC"),
    ("NEX-SRC", "NEX-EGC"), ("NEX-MOC", "NEX-EGC"), ("NEX-TRN", "NEX-EGC"), ("NEX-CMC", "NEX-EGC"),
    ("NEX-EGC", "NEX-REC"), ("NEX-REC", "NEX-INV"), ("NEX-INV", "NEX-RPT"),
}


def test_edges_equal_flowchart_a1():
    assert len(ModuleCatalog.EDGES) == len(set(ModuleCatalog.EDGES)) == 31
    assert set(ModuleCatalog.EDGES) == A1_EDGES
    assert ("NEX-SRC", "NEX-MOC") in ModuleCatalog.EDGES


def test_eighteen_modules_twelve_coordinated_and_acyclic():
    ids = [m.module_id for m in ModuleCatalog.MODULES]
    assert len(ids) == len(set(ids)) == 18
    assert [m.number for m in ModuleCatalog.MODULES] == list(range(1, 19))
    assert {a for edge in A1_EDGES for a in edge} <= set(ids)
    assert set(ModuleCatalog.TMIR_COORDINATED) == {
        "NEX-MET", "NEX-IMG", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-FPM", "NEX-MOC", "NEX-ALN", "NEX-TRN", "NEX-CMC", "NEX-EGC", "NEX-REC"
    }
    assert all(m.executed_by == "T-MIR" for m in ModuleCatalog.MODULES if m.module_id in ModuleCatalog.TMIR_COORDINATED)
    order = ModuleCatalog.topological_order()
    assert order.index("NEX-SRC") < order.index("NEX-MOC") < order.index("NEX-ALN") < order.index("NEX-RPT")


def test_modules_endpoint(database_down_app):
    with TestClient(database_down_app) as client:  # needs no database
        body = client.get("/api/v1/system/modules").json()["data"]
    assert len(body["modules"]) == 18
    src = next(m for m in body["modules"] if m["module_id"] == "NEX-SRC")
    assert src["upstream"] == [] and set(src["downstream"]) == {"NEX-FPM", "NEX-MOC", "NEX-EGC"}
    assert body["tmir"]["status"] == "PARTIAL" and len(body["tmir"]["coordinates"]) == 12
    assert body["execution_tracking"] == "PERSISTED"
    statuses = {m["module_id"]: m["status"] for m in body["modules"]}
    assert statuses["NEX-CM"] == statuses["NEX-CAP"] == statuses["NEX-EVD"] == "IMPLEMENTED"
    assert statuses["NEX-MET"] == "PARTIAL"
    assert statuses["NEX-IMG"] == statuses["NEX-VID"] == statuses["NEX-AUD"] == "PARTIAL" and statuses["NEX-PRV"] == "IMPLEMENTED"
    assert sum(s == "NOT_IMPLEMENTED" for s in statuses.values()) == 10
