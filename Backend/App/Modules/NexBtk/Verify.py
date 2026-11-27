"""Bounded media checks. A match means shared content, never provenance."""
from pathlib import Path
from collections import Counter

import numpy as np
from PIL import Image, ImageOps

from Backend.App.Modules.NexBtk import VideoMatch
from Backend.App.Modules.NexFpm import Fingerprints as F
from Backend.App.Utils import MediaDecode

VERSION = "nextron-btk-verify/1"
LIMITATIONS = ["A content match does not establish origin, direction, or publication order",
               "Sampling and fixed transform hypotheses can miss edited content"]


def _image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source.load()
        return ImageOps.exif_transpose(source).convert("L")


def _visual(a: Image.Image, b: Image.Image) -> dict:
    if min(np.asarray(a.resize((32, 32))).std(), np.asarray(b.resize((32, 32))).std()) < 5:
        return {"status": "INCONCLUSIVE", "reason": "LOW_VISUAL_DIVERSITY", "method": "image perceptual hashes"}
    ap, ad = F.image_hashes(a)
    trials = [("unaltered", b)]
    for rotation in (90, 180, 270):
        trials.append((f"rotate_{rotation}", b.rotate(rotation, expand=True)))
    trials.append(("mirror", ImageOps.mirror(b)))
    for ratio in (.9, .75, .5):
        for name, image in (("seed", a), ("candidate", b)):
            w, h = image.size
            crop = image.crop((int(w * (1-ratio)/2), int(h * (1-ratio)/2),
                               int(w * (1+ratio)/2), int(h * (1+ratio)/2)))
            trials.append((f"{name}_center_crop_{ratio:g}", crop))
    best = None
    for label, image in trials:
        # When the seed is cropped, compare the candidate against the cropped seed.
        if label.startswith("seed_"):
            cp, cd = F.image_hashes(image)
            bp, bd = F.image_hashes(b)
        else:
            cp, cd = ap, ad
            bp, bd = F.image_hashes(image)
        distances = (F.hamming(cp, bp), F.hamming(cd, bd))
        if best is None or sum(distances) < sum(best[1]):
            best = (label, distances)
    label, (pd, dd) = best
    return {"status": "CANDIDATE_MATCH" if pd <= F.PHASH_MATCH and dd <= F.DHASH_MATCH else "NO_VERIFIED_LOCAL_MATCH",
            "method": "image perceptual hashes with bounded rotations, mirror, and center crops",
            "transformation": label, "phash_distance": pd, "dhash_distance": dd,
            "thresholds": {"phash": F.PHASH_MATCH, "dhash": F.DHASH_MATCH}}


def _audio(a: Path, b: Path, ffprobe: str, timeout: float) -> dict:
    pa = F.fingerprint_audio(a, ffprobe=ffprobe, timeout=timeout).get("AUDIO_SUBFINGERPRINT")
    pb = F.fingerprint_audio(b, ffprobe=ffprobe, timeout=timeout).get("AUDIO_SUBFINGERPRINT")
    if not pa or not pb:
        return {"status": "INCONCLUSIVE", "reason": "AUDIO_UNAVAILABLE_OR_TOO_SHORT", "method": "audio sub-fingerprints"}
    match = F.audio_match(np.asarray(pa["values"], dtype=np.uint32), np.asarray(pb["values"], dtype=np.uint32))
    if match is None:
        return {"status": "INCONCLUSIVE", "reason": "INSUFFICIENT_AUDIO", "method": "audio sub-fingerprints"}
    ber, rows = match
    return {"status": "CANDIDATE_MATCH" if ber <= F.AUDIO_BER_MATCH else "NO_VERIFIED_LOCAL_MATCH",
            "method": "audio sub-fingerprints", "bit_error_rate": round(ber, 4),
            "threshold": F.AUDIO_BER_MATCH, "offset_s": round(rows * F.AUDIO_HOP / F.AUDIO_RATE, 3)}


def _speed(a: Path, b: Path, ffprobe: str, timeout: float) -> dict:
    fa = F.fingerprint_video(a, ffprobe=ffprobe, timeout=timeout).get("VIDEO_FRAME_DHASH", {}).get("frames", [])
    fb = F.fingerprint_video(b, ffprobe=ffprobe, timeout=timeout).get("VIDEO_FRAME_DHASH", {}).get("frames", [])
    if min(len({f["phash"] for f in fa}), len({f["phash"] for f in fb})) < 3:
        return {"status": "INCONCLUSIVE", "reason": "LOW_VISUAL_DIVERSITY", "method": "speed hypotheses"}
    raw = [(x, y) for x in fa for y in fb if F.hamming(x["phash"], y["phash"]) <= F.PHASH_MATCH
           and F.hamming(x["dhash"], y["dhash"]) <= F.DHASH_MATCH]
    if not raw:
        return {"status": "INCONCLUSIVE", "reason": "INSUFFICIENT_DISTINCT_FRAME_MATCHES",
                "method": "speed hypotheses", "tested_speeds": [.5, .75, 1, 1.25, 1.5, 2]}
    best = (0, None, None)
    for speed in (.5, .75, 1.0, 1.25, 1.5, 2.0):
        offsets = Counter(round(y["t"] - speed * x["t"]) for x, y in raw)
        for offset, _ in offsets.most_common(5):
            pairs = [(x["t"], y["t"]) for x, y in raw if abs(y["t"] - speed * x["t"] - offset) <= .55]
            pairs.sort()
            chosen, last_b = [], -float("inf")
            for ta, tb in pairs:
                if (not chosen or ta > chosen[-1][0]) and tb > last_b:
                    chosen.append((ta, tb)); last_b = tb
            if len(chosen) > best[0]:
                best = (len(chosen), speed, offset)
    count, speed, offset = best
    required = max(3, int(np.ceil(.3 * min(len(fa), len(fb)))))
    return {"status": "CANDIDATE_MATCH" if count >= required else "NO_VERIFIED_LOCAL_MATCH",
            "method": "monotonic frame matches over fixed speed hypotheses", "matched_frames": count,
            "speed": speed if count >= required else None, "offset_s": offset if count >= required else None,
            "tested_speeds": [.5, .75, 1, 1.25, 1.5, 2]}


def _geometry(a: Path, b: Path, ffprobe: str, timeout: float) -> dict:
    ffmpeg = MediaDecode.ffmpeg_for(ffprobe)
    sa = MediaDecode.sample_frames(a, ffmpeg, timeout, fps=1, max_frames=12, width=128)
    sb = MediaDecode.sample_frames(b, ffmpeg, timeout, fps=1, max_frames=12, width=128)
    if len(sa.frames) < 3 or len(sb.frames) < 3:
        return {"status": "INCONCLUSIVE", "reason": "INSUFFICIENT_FRAMES", "method": "sampled frame geometry"}
    trials = []
    usable = 0
    for i, frame in enumerate(sa.frames):
        for j, other in enumerate(sb.frames):
            result = _visual(Image.fromarray(frame), Image.fromarray(other))
            usable += result["status"] != "INCONCLUSIVE"
            if result["status"] == "CANDIDATE_MATCH":
                trials.append({"seed_t_s": sa.times[i], "candidate_t_s": sb.times[j],
                               "transformation": result["transformation"]})
    distinct = len({p["seed_t_s"] for p in trials})
    return {"status": "CANDIDATE_MATCH" if distinct >= 3 else ("NO_VERIFIED_LOCAL_MATCH" if usable else "INCONCLUSIVE"),
            "method": "sampled frame crop, mirror, rotation hypotheses", "matched_frames": distinct,
            "frame_pairs": trials[:24], "sample_limit_per_video": 12}


def verify(a: Path, b: Path, media_a: str, media_b: str, *, ffprobe: str, timeout: float) -> dict:
    checks = {}
    if media_a == media_b == "IMAGE":
        checks["image"] = _visual(_image(a), _image(b))
    elif media_a == media_b == "VIDEO":
        checks["video"] = VideoMatch.compare(a, b, ffprobe=ffprobe, timeout=timeout)
        checks["speed"] = _speed(a, b, ffprobe, timeout)
        if checks["video"]["status"] != "CANDIDATE_MATCH":
            checks["geometry"] = _geometry(a, b, ffprobe, timeout)
        checks["audio"] = _audio(a, b, ffprobe, timeout)
    elif media_a in ("VIDEO", "AUDIO") and media_b in ("VIDEO", "AUDIO"):
        checks["audio"] = _audio(a, b, ffprobe, timeout)
    else:
        return {"algorithm": VERSION, "status": "INCONCLUSIVE", "reason": "UNSUPPORTED_MEDIA_PAIR",
                "checks": {}, "limitations": LIMITATIONS}
    states = {check["status"] for check in checks.values()}
    status = "CANDIDATE_MATCH" if "CANDIDATE_MATCH" in states else (
        "NO_VERIFIED_LOCAL_MATCH" if "NO_VERIFIED_LOCAL_MATCH" in states else "INCONCLUSIVE")
    return {"algorithm": VERSION, "fingerprint_algorithm": F.ALGORITHM, "status": status,
            "checks": checks, "limitations": LIMITATIONS}
