"""Local benchmark facts quoted in every detector finding, and the threshold each finding compares against.

Source: Documentation/Testing/Detector Benchmark.md and Benchmarks/Results/*.json (every item's score is kept, so
each figure can be recomputed). A threshold is either the model's own (0.5, what it was trained with) or one
measured here on real-world data, and every finding says which.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Operating:
    threshold: float
    source: str
    summary: str


OPERATING = {
    "CommunityForensics-ViT-S16-384": Operating(
        0.5, "the model's own threshold",
        "ROC AUC 0.997, EER 2.6 % on 500 CommunityForensics-Eval images (GAN fakes only; the authors' own evaluation set); "
        "at 0.5, 4.5 % of real images and 8 % of RAISE camera photos were flagged"),
    "SSL-AASIST-DF": Operating(
        0.99970943, "the equal-error-rate threshold measured on In-the-Wild (the model's own 0.5 flags most real speech)",
        "ROC AUC 0.966, EER 8.0 % on 800 In-the-Wild clips (real-world celebrity and politician deepfakes); at this "
        "threshold 8.5 % of real clips were flagged and 92.5 % of fakes; scores are saturated, so small processing "
        "differences can move a clip across it"),
}


def operating(detector: str) -> Operating:
    return OPERATING.get(detector, Operating(0.5, "the model's own threshold", "not benchmarked in this installation"))


def summary(detector: str) -> str:
    return operating(detector).summary
