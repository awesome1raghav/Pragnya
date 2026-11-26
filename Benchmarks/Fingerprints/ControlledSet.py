"""NEX-FPM precision and recall on a controlled set (Implementation Plan, Step 5 "done when").

    .\\.venv\\Scripts\\python.exe -m Benchmarks.Fingerprints.ControlledSet

Base images are real photographs from the downloaded CommunityForensics-Eval shards (label 0 only). Each base gets
five benign variants (half size, JPEG quality 60, 90 % centre crop, +20 % brightness, a 5-pixel border); positives
are base-variant pairs, negatives are pairs of different base photographs (and their variants). Writes
Benchmarks/Results/Fingerprints.json with per-threshold precision and recall.
"""

import io
import itertools
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from Backend.App.Modules.NexFpm import Fingerprints as F

ROOT = Path(__file__).resolve().parents[2]
SHARDS = ROOT / "Benchmarks" / "Data" / "CommunityForensicsEval" / "data"
BASES, DISTRACTORS, SEED = 60, 120, 20261126

VARIANTS = {
    "half_size": lambda im: im.resize((im.width // 2, im.height // 2), Image.Resampling.BILINEAR),
    "jpeg_q60": lambda im: Image.open(io.BytesIO(_jpeg(im, 60))),
    "crop_90": lambda im: im.crop((im.width // 20, im.height // 20, im.width - im.width // 20, im.height - im.height // 20)),
    "brighter_20": lambda im: ImageEnhance.Brightness(im).enhance(1.2),
    "border_5px": lambda im: ImageOps.expand(im, border=5, fill=(255, 255, 255)),
}


def _jpeg(im: Image.Image, q: int) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=q)
    return buf.getvalue()


def real_photos() -> list[Image.Image]:
    import pyarrow.parquet as pq

    photos = []
    for shard in sorted(SHARDS.glob("*.parquet")):
        for r in pq.read_table(shard, columns=["image_data", "label"]).to_pylist():
            if r["label"] == 0:
                data = r["image_data"]["bytes"] if isinstance(r["image_data"], dict) else r["image_data"]
                im = Image.open(io.BytesIO(data)).convert("RGB")
                im.thumbnail((1024, 1024))
                photos.append(im)
    return photos


def hashes(im: Image.Image) -> tuple[int, int]:
    return F.image_hashes(ImageOps.exif_transpose(im).convert("L"))


def main() -> dict:
    photos = real_photos()
    rng = random.Random(SEED)
    rng.shuffle(photos)
    bases, distractors = photos[:BASES], photos[BASES:BASES + DISTRACTORS]
    items = []  # (group, variant, phash, dhash)
    for g, im in enumerate(bases):
        items.append((g, "original", *hashes(im)))
        for name, fn in VARIANTS.items():
            items.append((g, name, *hashes(fn(im))))
    for k, im in enumerate(distractors):
        items.append((BASES + k, "distractor", *hashes(im)))
    pos, neg = [], []
    for a, b in itertools.combinations(items, 2):
        d = (F.hamming(a[2], b[2]), F.hamming(a[3], b[3]), a[1] if a[1] != "original" else b[1])
        (pos if a[0] == b[0] else neg).append(d)
    pos_a, neg_a = np.array([p[:2] for p in pos]), np.array([n[:2] for n in neg])
    rows = []
    for tp_, td_ in [(6, 10), (8, 12), (10, 14), (12, 16), (14, 18), (16, 20)]:
        tp = int(((pos_a[:, 0] <= tp_) & (pos_a[:, 1] <= td_)).sum())
        fp = int(((neg_a[:, 0] <= tp_) & (neg_a[:, 1] <= td_)).sum())
        rows.append({"phash_le": tp_, "dhash_le": td_, "recall": round(tp / len(pos), 4), "precision": round(tp / max(tp + fp, 1), 4),
                     "false_positives": fp, "true_positives": tp})
    by_variant = {}
    for name in VARIANTS:
        sel = np.array([p[2] == name for p in pos])
        sub = pos_a[sel]
        by_variant[name] = {"pairs": int(sel.sum()), "recall_at_chosen": round(float(((sub[:, 0] <= F.PHASH_MATCH) & (sub[:, 1] <= F.DHASH_MATCH)).mean()), 4),
                            "median_phash": float(np.median(sub[:, 0]))}
    result = {"bases": BASES, "variants_per_base": len(VARIANTS), "distractors": DISTRACTORS, "positive_pairs": len(pos), "negative_pairs": len(neg),
              "chosen": {"phash_le": F.PHASH_MATCH, "dhash_le": F.DHASH_MATCH}, "thresholds": rows, "by_variant": by_variant,
              "source": "real photographs from CommunityForensics-Eval (label 0), CC BY-NC-SA 4.0, internal evaluation"}
    (ROOT / "Benchmarks" / "Results").mkdir(parents=True, exist_ok=True)
    (ROOT / "Benchmarks" / "Results" / "Fingerprints.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return result


if __name__ == "__main__":
    main()
