"""Verify two preserved videos using real sampled frames and temporal consistency.

This first slice compares local media only. Coverage is sampled-frame coverage,
not a calibrated probability or proof of parentage.
"""
import subprocess
import json
from pathlib import Path

import numpy as np

from Backend.App.Modules.NexFpm import Fingerprints as F

VERSION = "nextron-btk-video/1"


def _duration(path: Path, ffprobe: str) -> float:
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def compare(seed: Path, candidate: Path, *, ffprobe: str = "ffprobe", timeout: float = 60) -> dict:
    a = F.fingerprint_video(seed, ffprobe=ffprobe, timeout=timeout).get("VIDEO_FRAME_DHASH", {}).get("frames", [])
    b = F.fingerprint_video(candidate, ffprobe=ffprobe, timeout=timeout).get("VIDEO_FRAME_DHASH", {}).get("frames", [])
    da, db = _duration(seed, ffprobe), _duration(candidate, ffprobe)
    # Repetitive/flat footage cannot support a reliable offset or source identity.
    diversity = (len({f["phash"] for f in a}), len({f["phash"] for f in b}))
    raw = [(i, j, F.hamming(x["phash"], y["phash"]), F.hamming(x["dhash"], y["dhash"]))
           for i, x in enumerate(a) for j, y in enumerate(b)]
    raw = [p for p in raw if p[2] <= F.PHASH_MATCH and p[3] <= F.DHASH_MATCH]
    if min(diversity, default=0) < 3:
        raw = []
    # Test each time-offset hypothesis, choosing a one-to-one monotonic sequence.
    offsets = sorted({round(b[j]["t"] - a[i]["t"]) for i,j,_,_ in raw})
    hypotheses = []
    for offset in offsets:
        pairs = sorted((p for p in raw if abs((b[p[1]]["t"] - a[p[0]]["t"]) - offset) <= 0.5),
                       key=lambda p: (p[2] + p[3], p[0], p[1]))
        used_a, used_b, chosen = set(), set(), []
        for p in pairs:
            if p[0] not in used_a and p[1] not in used_b:
                used_a.add(p[0]); used_b.add(p[1]); chosen.append(p)
        chosen.sort(key=lambda p: p[0])
        if all(chosen[k][1] < chosen[k+1][1] for k in range(len(chosen)-1)):
            hypotheses.append((chosen, offset))
    chosen, offset = max(hypotheses, key=lambda h: (len(h[0]), -sum(p[2]+p[3] for p in h[0]))) if hypotheses else ([], None)
    if len(chosen) < max(3, int(np.ceil(0.3 * min(len(a), len(b))))):
        chosen, offset = [], None
    matches = [{"seed_t_s":a[i]["t"], "candidate_t_s":b[j]["t"], "phash_distance":pd, "dhash_distance":dd}
               for i,j,pd,dd in chosen]
    intervals = []
    for match in matches:
        sa, ca = match["seed_t_s"], match["candidate_t_s"]
        sb, cb = min(sa + 1 / F.VIDEO_FPS, da), min(ca + 1 / F.VIDEO_FPS, db)
        if intervals and sa <= intervals[-1]["seed_end_s"] + 0.001 and ca <= intervals[-1]["candidate_end_s"] + 0.001:
            intervals[-1]["seed_end_s"] = max(intervals[-1]["seed_end_s"], sb)
            intervals[-1]["candidate_end_s"] = max(intervals[-1]["candidate_end_s"], cb)
        else:
            intervals.append({"seed_start_s":sa, "seed_end_s":sb, "candidate_start_s":ca, "candidate_end_s":cb})
    seed_matched_s = sum(i["seed_end_s"] - i["seed_start_s"] for i in intervals)
    candidate_matched_s = sum(i["candidate_end_s"] - i["candidate_start_s"] for i in intervals)
    inconclusive = min(diversity, default=0) < 3 or not a or not b
    return {"algorithm":VERSION, "fingerprint_algorithm":F.ALGORITHM, "sample_rate_fps":F.VIDEO_FPS,
            "seed_duration_s":da, "candidate_duration_s":db, "seed_sampled_frames":len(a), "candidate_sampled_frames":len(b),
            "seed_unique_frame_hashes":diversity[0], "candidate_unique_frame_hashes":diversity[1],
            "matched_frames":len(chosen), "matched_duration_estimate_s":min(seed_matched_s, candidate_matched_s),
            "submitted_coverage_percent":round(100 * seed_matched_s / da, 2) if da and not inconclusive else None,
            "candidate_coverage_percent":round(100 * candidate_matched_s / db, 2) if db and not inconclusive else None,
            "offset_s":offset, "frame_pairs":matches, "matched_intervals":intervals,
            "status":"INCONCLUSIVE" if inconclusive else ("CANDIDATE_MATCH" if chosen else "NO_VERIFIED_LOCAL_MATCH"),
            "limitations":["Coverage is estimated at one sampled frame per second; gaps shorter than one second can be missed",
                           "Perceptual hashes and time consistency are not geometric verification or proof of derivation",
                           "Flat/repetitive footage is rejected when frame hashes lack diversity"]}
