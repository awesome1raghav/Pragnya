"""The dependency registry against the canonical flowchart, plus its planning rules.

The edge test reads the Mermaid source stored in Documentation/Architecture/Module Connectivity.md, so the
document and the code cannot drift apart without this test failing.
"""

import itertools
import random
import re

import pytest

from Backend.App.Config import PROJECT_ROOT
from Backend.App.Contracts.ExecutionStates import ExecutionState as S, SkipReason
from Backend.App.Orchestration.TMir import DependencyRegistry as R
from Backend.App.Orchestration.TMir.DependencyRegistry import Action, EdgeKind, EvidenceFacts

DOC = PROJECT_ROOT / "Documentation" / "Architecture" / "Module Connectivity.md"


def mermaid_blocks() -> list[str]:
    return re.findall(r"```mermaid\n(.*?)```", DOC.read_text(encoding="utf-8"), flags=re.S)


def parse(block: str) -> tuple[set[tuple[str, str]], set[str]]:
    """Solid module edges (chains expanded) and the targets of T-MIR's dotted edges."""
    solid, dotted = set(), set()
    for raw in block.splitlines():
        line = raw.strip()
        if line.startswith("TMIR") and "-." in line:
            dotted.add(re.split(r"\.->\s*", line)[-1].strip())
            continue
        if "-->" not in line or "-." in line:
            continue
        nodes = [re.match(r"[A-Z]+", part.strip()).group(0) for part in line.split("-->")]
        for a, b in itertools.pairwise(nodes):
            if a not in ("START",) and b not in ("END",):
                solid.add((f"NEX-{a}", f"NEX-{b}"))
    return solid, {f"NEX-{t}" for t in dotted}


def test_document_holds_both_flowcharts():
    blocks = mermaid_blocks()
    assert len(blocks) == 2
    assert blocks[0].startswith("flowchart TD") and "T-MIR ORCHESTRATION" in blocks[0]
    assert blocks[1].startswith("flowchart TB") and "NEX-TMIR<br/>CENTRAL INTELLIGENCE" in blocks[1]


def test_registry_edges_equal_flowchart_a1_exactly():
    a1_solid, a1_dotted = parse(mermaid_blocks()[0])
    assert len(a1_solid) == 31
    assert set(R.solid_edges()) == a1_solid
    assert set(R.TMIR_COORDINATED) == a1_dotted and len(a1_dotted) == 12


def test_flowchart_a2_differs_only_by_src_to_moc_and_tmir_scope():
    a1_solid, _ = parse(mermaid_blocks()[0])
    a2_solid, a2_dotted = parse(mermaid_blocks()[1])
    assert a1_solid - a2_solid == {("NEX-SRC", "NEX-MOC")}  # conflict C-2: A1 wins
    assert a2_solid - a1_solid == set()
    assert len(a2_dotted) == 18 and set(R.TMIR_COORDINATED) < a2_dotted  # conflict C-1: T-MIR executes A1's twelve


def test_graph_is_acyclic_and_a_cycle_is_rejected(monkeypatch):
    order = R.topological_order()
    assert order.index("NEX-SRC") < order.index("NEX-MOC") < order.index("NEX-ALN") < order.index("NEX-TRN") < order.index("NEX-CMC") < order.index("NEX-EGC") < order.index("NEX-RPT")
    monkeypatch.setattr(R, "EDGES", R.EDGES + (R.Edge("NEX-RPT", "NEX-CM", EdgeKind.OPTIONAL, "loop"),))
    with pytest.raises(ValueError, match="cycle"):
        R.topological_order()


def test_validate_rejects_a_broken_registry(monkeypatch):
    R.validate()
    monkeypatch.setattr(R, "EDGES", R.EDGES + (R.Edge("NEX-CM", "NEX-XYZ", EdgeKind.OPTIONAL, "unknown"),))
    with pytest.raises(ValueError, match="unknown module"):
        R.validate()


def test_edge_types_follow_the_plan():
    kind = {(e.upstream, e.downstream): e.kind for e in R.EDGES}
    assert kind[("NEX-FPM", "NEX-MOC")] is EdgeKind.REQUIRED
    assert kind[("NEX-SRC", "NEX-MOC")] is EdgeKind.OPTIONAL
    assert kind[("NEX-IMG", "NEX-FPM")] is EdgeKind.CONDITIONAL
    assert kind[("NEX-MOC", "NEX-ALN")] is EdgeKind.REQUIRED
    assert kind[("NEX-ALN", "NEX-TRN")] is EdgeKind.CONDITIONAL
    assert kind[("NEX-EGC", "NEX-REC")] is EdgeKind.REQUIRED
    assert all(kind[(u, "NEX-CMC")] is EdgeKind.OPTIONAL for u in ("NEX-IMG", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-TRN"))
    assert all(e.reason for e in R.EDGES)


@pytest.mark.parametrize(
    ("media", "mime", "applies"),
    [
        ("IMAGE", "image/png", {"NEX-MET", "NEX-IMG", "NEX-PRV", "NEX-FPM"}),
        ("VIDEO", "video/mp4", {"NEX-MET", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-FPM"}),
        ("AUDIO", "audio/flac", {"NEX-MET", "NEX-AUD", "NEX-PRV", "NEX-FPM"}),
        ("AUDIO", "audio/ogg", {"NEX-MET", "NEX-AUD", "NEX-FPM"}),  # the C2PA SDK cannot read Ogg
    ],
)
def test_applicability_per_media_type(media, mime, applies):
    facts = EvidenceFacts(media, mime)
    evidence_scoped = [m.module_id for m in R.MODULES if m.scope is R.Scope.EVIDENCE]
    assert {m for m in evidence_scoped if R.applies_to(m, facts)} == applies


def ups(**states):
    return {f"NEX-{k}": v for k, v in states.items()}


def test_image_fingerprinting_runs_on_image_features_alone():
    d = R.decide("NEX-FPM", applicable=True, upstream=ups(MET=S.COMPLETED, IMG=S.COMPLETED),
                 upstream_applicable=ups(IMG=True, VID=False, AUD=False))
    assert d.action is Action.RUN and set(d.using) == {"NEX-MET", "NEX-IMG"}
    assert "NEX-SRC was not part of this run" in d.limitations


def test_waiting_failed_and_inapplicable_branches():
    applic = ups(IMG=True, VID=False, AUD=False)
    assert R.decide("NEX-FPM", applicable=True, upstream=ups(MET=S.COMPLETED, IMG=S.RUNNING), upstream_applicable=applic).action is Action.WAIT
    assert R.decide("NEX-FPM", applicable=True, upstream=ups(MET=S.COMPLETED, IMG=None), upstream_applicable=applic).action is Action.WAIT
    failed = R.decide("NEX-FPM", applicable=True, upstream=ups(MET=S.COMPLETED, IMG=S.FAILED), upstream_applicable=applic)
    assert (failed.action, failed.reason) == (Action.SKIP, SkipReason.UPSTREAM_FAILED)
    unavailable = R.decide("NEX-FPM", applicable=True, upstream=ups(MET=S.COMPLETED, IMG=S.UNAVAILABLE), upstream_applicable=applic)
    assert (unavailable.action, unavailable.reason) == (Action.SKIP, SkipReason.NO_INPUT)
    na = R.decide("NEX-AUD", applicable=False, upstream=ups(EVD=S.COMPLETED))
    assert (na.action, na.reason) == (Action.SKIP, SkipReason.NOT_APPLICABLE)


def test_required_upstream_outcomes():
    assert R.decide("NEX-MOC", applicable=True, upstream=ups(FPM=S.COMPLETED)).action is Action.RUN
    assert R.decide("NEX-MOC", applicable=True, upstream=ups(FPM=S.PARTIALLY_COMPLETED)).limitations[0] == "NEX-FPM completed only partially"
    assert R.decide("NEX-MOC", applicable=True, upstream=ups(FPM=S.FAILED)).reason is SkipReason.UPSTREAM_FAILED
    assert R.decide("NEX-MOC", applicable=True, upstream=ups(FPM=S.SKIPPED)).reason is SkipReason.NO_INPUT
    assert R.decide("NEX-MOC", applicable=True, upstream={}).reason is SkipReason.NO_INPUT
    # a required failure decides immediately even while an optional upstream is still running
    early = R.decide("NEX-MOC", applicable=True, upstream=ups(FPM=S.FAILED, SRC=S.RUNNING))
    assert early.action is Action.SKIP


def test_correlation_and_graph_tolerate_missing_branches():
    cmc = R.decide("NEX-CMC", applicable=True, upstream=ups(PRV=S.COMPLETED, TRN=S.SKIPPED), upstream_applicable=ups(IMG=False, VID=False, AUD=False))
    assert cmc.action is Action.RUN and cmc.using == ["NEX-PRV"]
    none = R.decide("NEX-CMC", applicable=True, upstream=ups(IMG=S.FAILED, PRV=S.UNAVAILABLE, TRN=S.SKIPPED))
    assert none.action is Action.SKIP
    egc = R.decide("NEX-EGC", applicable=True, upstream=ups(MOC=S.SKIPPED, TRN=S.SKIPPED, CMC=S.FAILED))
    assert egc.action is Action.RUN and len(egc.limitations) == 4  # SRC not in run + three ended without output


OUTCOMES = [S.COMPLETED, S.PARTIALLY_COMPLETED, S.FAILED, S.UNAVAILABLE]


@pytest.mark.parametrize("media,mime", [("IMAGE", "image/jpeg"), ("VIDEO", "video/mp4"), ("AUDIO", "audio/wav")])
def test_no_run_can_deadlock(media, mime):
    """Simulate 300 runs with random module outcomes: once every upstream has ended, no module is left waiting."""
    rng = random.Random(f"{media}-seed")
    facts = EvidenceFacts(media, mime)
    for _ in range(300):
        states: dict[str, S] = {"NEX-CM": S.COMPLETED, "NEX-CAP": S.COMPLETED, "NEX-EVD": S.COMPLETED}
        if rng.random() < .5:
            states["NEX-SRC"] = rng.choice(OUTCOMES)
        applic = {m.module_id: R.applies_to(m.module_id, facts) for m in R.MODULES if m.scope is R.Scope.EVIDENCE}
        for mid in R.topological_order():
            if R.spec(mid).owner is not R.Owner.TMIR:
                continue
            upstream = {e.upstream: states[e.upstream] for e in R.upstream_edges(mid) if e.upstream in states}
            d = R.decide(mid, applicable=applic.get(mid, True), upstream=upstream, upstream_applicable=applic)
            assert d.action is not Action.WAIT, f"{mid} would wait forever with {upstream}"
            states[mid] = rng.choice(OUTCOMES) if d.action is Action.RUN else S.SKIPPED
        assert all(states[m].terminal for m in R.TMIR_COORDINATED)


def test_c2pa_list_is_confirmed_by_the_installed_sdk():
    import c2pa
    assert R.C2PA_MIME_TYPES <= set(c2pa.Reader.get_supported_mime_types())
