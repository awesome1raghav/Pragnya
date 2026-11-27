"""Controlled real-media backtracking slice; these are measured candidate results."""
from pathlib import Path

from Backend.App.Modules.NexBtk.VideoMatch import compare

CORPUS = Path(__file__).resolve().parents[2] / "QA-Audit" / "NEXTRON-QA-001"


def test_related_versions_and_unrelated_control():
    original = CORPUS / "VID-01.mp4"
    resized = compare(original, CORPUS / "VID-02.mp4")
    trimmed = compare(original, CORPUS / "VID-03.mp4")
    unrelated = compare(original, CORPUS / "VID-04.mp4")
    assert resized["status"] == "CANDIDATE_MATCH"
    assert resized["matched_frames"] == 12
    assert resized["submitted_coverage_percent"] == 100
    assert resized["candidate_coverage_percent"] == 100
    assert resized["matched_intervals"] == [{"seed_start_s": 0.0, "seed_end_s": 12.0,
                                            "candidate_start_s": 0.0, "candidate_end_s": 12.0}]
    assert trimmed["status"] == "CANDIDATE_MATCH"
    assert trimmed["matched_frames"] == 10
    assert trimmed["submitted_coverage_percent"] == 83.33
    assert trimmed["candidate_coverage_percent"] == 100
    assert trimmed["offset_s"] == -2
    assert trimmed["matched_intervals"] == [{"seed_start_s": 2.0, "seed_end_s": 12.0,
                                            "candidate_start_s": 0.0, "candidate_end_s": 10.0}]
    assert all(abs(p["candidate_t_s"] - (p["seed_t_s"] - 2)) <= .5 for p in trimmed["frame_pairs"])
    assert unrelated["status"] == "INCONCLUSIVE"
    assert unrelated["submitted_coverage_percent"] is None


def test_deterministic_repeated_comparison():
    a = compare(CORPUS / "VID-01.mp4", CORPUS / "VID-03.mp4")
    b = compare(CORPUS / "VID-01.mp4", CORPUS / "VID-03.mp4")
    assert a == b
