"""NEX-FPM canonical fingerprints and their comparison (archive §4, module 10).

Every evidence item is fingerprinted from its preserved original with the same functions, so an image can be
compared with a video frame and one recording's audio with another's:

  IMAGE_PHASH / IMAGE_DHASH   64-bit DCT hash and difference hash of the grayscale image (32x32 and 9x8 Lanczos).
  VIDEO_FRAME_DHASH           both hashes for one frame per second (FFmpeg presentation timestamps kept).
  AUDIO_SUBFINGERPRINT        Philips-style 32-bit sub-fingerprints (Haitsma & Kalker 2002): signs of energy
                              differences across 33 log-spaced bands, 300–2000 Hz, every 32 ms of 16 kHz mono audio.

Comparison returns distances, never verdicts: Hamming distance for the 64-bit hashes, bit error rate (BER) at the
best time offset for audio. Thresholds were set on the controlled set in Tests/Integration/Engines/test_fingerprints.py
and are stated with every candidate. Similar fingerprints mean similar content, not common origin.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from Backend.App.Utils import MediaDecode

ALGORITHM = "nextron-fpm/1"
PHASH_MATCH = 12        # Hamming distance (of 64) at or below which two images/frames are near-duplicates
DHASH_MATCH = 16
AUDIO_BER_MATCH = 0.30  # bit error rate at or below which two audio segments match (random audio: about 0.5)
AUDIO_BLOCK = 128       # sub-fingerprints per comparison block (about 4.1 s)
VIDEO_FPS = 1.0
MAX_FRAMES = 600
AUDIO_RATE, AUDIO_FRAME, AUDIO_HOP = 16_000, 2048, 512
MAX_AUDIO_SECONDS = 600


def _bits_to_int(bits: np.ndarray) -> int:
    value = 0
    for b in bits.flatten():
        value = (value << 1) | int(bool(b))
    return value


_DCT = np.cos(np.pi * (2 * np.arange(32)[None, :] + 1) * np.arange(32)[:, None] / 64)


def image_hashes(gray: Image.Image) -> tuple[int, int]:
    """(pHash, dHash) of a grayscale image."""
    p = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    coeffs = (_DCT @ p @ _DCT.T)[:8, :8]
    phash = _bits_to_int(coeffs > np.median(coeffs.flatten()[1:]))
    d = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.float64)
    return phash, _bits_to_int(d[:, 1:] > d[:, :-1])


def fingerprint_image(path: Path) -> dict:
    with Image.open(path) as im:
        im.load()
        gray = ImageOps.exif_transpose(im).convert("L")
    phash, dhash = image_hashes(gray)
    return {"IMAGE_PHASH": {"hash": f"{phash:016x}"}, "IMAGE_DHASH": {"hash": f"{dhash:016x}"}}


def fingerprint_video(path: Path, *, ffprobe: str, timeout: float) -> dict:
    sampled = MediaDecode.sample_frames(path, MediaDecode.ffmpeg_for(ffprobe), timeout, fps=VIDEO_FPS, max_frames=MAX_FRAMES, width=256)
    frames = []
    for t, frame in zip(sampled.times, sampled.frames):
        phash, dhash = image_hashes(Image.fromarray(frame))
        frames.append({"t": round(t, 3), "phash": f"{phash:016x}", "dhash": f"{dhash:016x}"})
    return {"VIDEO_FRAME_DHASH": {"fps": VIDEO_FPS, "frames": frames}} if frames else {}


def audio_subfingerprints(samples: np.ndarray) -> np.ndarray:
    """uint32 sub-fingerprints of 16 kHz mono samples (empty when shorter than two frames)."""
    if samples.size < AUDIO_FRAME * 2:
        return np.zeros(0, dtype=np.uint32)
    edges = np.geomspace(300, 2000, 34)
    freqs = np.fft.rfftfreq(AUDIO_FRAME, 1 / AUDIO_RATE)
    band_of = np.digitize(freqs, edges) - 1  # -1 or 33 outside the 300–2000 Hz range
    window = np.hanning(AUDIO_FRAME)
    count = 1 + (samples.size - AUDIO_FRAME) // AUDIO_HOP
    energies = np.empty((count, 33))
    for start in range(0, count, 2048):
        idx = np.arange(start, min(start + 2048, count))
        power = np.abs(np.fft.rfft(samples[idx[:, None] * AUDIO_HOP + np.arange(AUDIO_FRAME)[None, :]] * window, axis=1)) ** 2
        for band in range(33):
            energies[idx, band] = power[:, band_of == band].sum(axis=1)
    diff = energies[:, :-1] - energies[:, 1:]                       # across frequency
    bits = (diff[1:] - diff[:-1]) > 0                                 # across time
    weights = (1 << np.arange(31, -1, -1, dtype=np.uint64))
    return (bits.astype(np.uint64) * weights).sum(axis=1).astype(np.uint32)


def fingerprint_audio(path: Path, *, ffprobe: str, timeout: float) -> dict:
    streams = MediaDecode.streams(path, ffprobe, timeout)
    if not any(s.get("codec_type") == "audio" for s in streams):
        return {}
    samples = MediaDecode.decode_audio(path, MediaDecode.ffmpeg_for(ffprobe), timeout, sample_rate=AUDIO_RATE, max_seconds=MAX_AUDIO_SECONDS)
    subs = audio_subfingerprints(samples)
    if subs.size < AUDIO_BLOCK:
        return {}
    return {"AUDIO_SUBFINGERPRINT": {"rate": AUDIO_RATE, "hop": AUDIO_HOP, "seconds_per_bit_row": AUDIO_HOP / AUDIO_RATE,
                                     "values": subs.tolist()}}


# ── comparison ───────────────────────────────────────────────────────────────────────────────

def hamming(a: int | str, b: int | str) -> int:
    a = int(a, 16) if isinstance(a, str) else a
    b = int(b, 16) if isinstance(b, str) else b
    return (a ^ b).bit_count()


@dataclass
class Match:
    kind: str                  # a RELATIONSHIP_KINDS value
    similarity: float          # 0..1
    measurement: dict
    offset_seconds: float | None = None


def compare(a: dict, b: dict) -> list[Match]:
    """All matches between two evidence items' fingerprints ({kind: value}), strongest first."""
    out: list[Match] = []
    ia, ib = "IMAGE_PHASH" in a, "IMAGE_PHASH" in b
    va, vb = "VIDEO_FRAME_DHASH" in a, "VIDEO_FRAME_DHASH" in b
    if ia and ib:
        dp, dd = hamming(a["IMAGE_PHASH"]["hash"], b["IMAGE_PHASH"]["hash"]), hamming(a["IMAGE_DHASH"]["hash"], b["IMAGE_DHASH"]["hash"])
        if dp <= PHASH_MATCH and dd <= DHASH_MATCH:
            kind = "NEAR_DUPLICATE" if dp <= 4 and dd <= 6 else "SAME_CONTENT_VARIANT"
            out.append(Match(kind, round(1 - dp / 64, 4), {"phash_distance": dp, "dhash_distance": dd,
                                                           "thresholds": {"phash": PHASH_MATCH, "dhash": DHASH_MATCH}}))
    if (ia and vb) or (va and ib):
        image, video = (a, b) if ia else (b, a)
        best = min(((hamming(image["IMAGE_PHASH"]["hash"], f["phash"]), hamming(image["IMAGE_DHASH"]["hash"], f["dhash"]), f["t"])
                    for f in video["VIDEO_FRAME_DHASH"]["frames"]), default=None)
        if best and best[0] <= PHASH_MATCH and best[1] <= DHASH_MATCH:
            out.append(Match("FRAME_OF_VIDEO", round(1 - best[0] / 64, 4),
                             {"phash_distance": best[0], "dhash_distance": best[1], "frame_time_s": best[2], "image_is": "a" if ia else "b"},
                             offset_seconds=best[2]))
    if va and vb:
        fa, fb = a["VIDEO_FRAME_DHASH"]["frames"], b["VIDEO_FRAME_DHASH"]["frames"]
        hb = np.array([int(f["phash"], 16) for f in fb], dtype=np.uint64)
        matches = []
        for f in fa:
            d = np.bitwise_count(hb ^ np.uint64(int(f["phash"], 16)))
            j = int(np.argmin(d))
            if d[j] <= PHASH_MATCH:
                matches.append((f["t"], fb[j]["t"], int(d[j])))
        shorter = min(len(fa), len(fb))
        if shorter and len(matches) >= max(2, 0.3 * shorter):
            offsets = np.array([tb - ta for ta, tb, _ in matches])
            out.append(Match("SHARED_VIDEO_SEGMENT", round(len(matches) / shorter, 4),
                             {"matched_frames": len(matches), "frames_a": len(fa), "frames_b": len(fb),
                              "median_offset_s": round(float(np.median(offsets)), 3), "mean_phash_distance": round(float(np.mean([m[2] for m in matches])), 2)},
                             offset_seconds=round(float(np.median(offsets)), 3)))
    if "AUDIO_SUBFINGERPRINT" in a and "AUDIO_SUBFINGERPRINT" in b:
        best = audio_match(np.array(a["AUDIO_SUBFINGERPRINT"]["values"], dtype=np.uint32),
                           np.array(b["AUDIO_SUBFINGERPRINT"]["values"], dtype=np.uint32))
        if best and best[0] <= AUDIO_BER_MATCH:
            seconds = AUDIO_HOP / AUDIO_RATE
            out.append(Match("SHARED_AUDIO", round(1 - best[0], 4),
                             {"bit_error_rate": round(best[0], 4), "threshold": AUDIO_BER_MATCH, "offset_s": round(best[1] * seconds, 3),
                              "block_seconds": round(AUDIO_BLOCK * seconds, 2)}, offset_seconds=round(best[1] * seconds, 3)))
    return sorted(out, key=lambda m: -m.similarity)


def audio_match(a: np.ndarray, b: np.ndarray) -> tuple[float, int] | None:
    """(lowest BER, offset in rows such that content at row r of `a` is at row r + offset of `b`).

    The shorter recording is cut into blocks (every quarter block) and each block is slid along the longer one, so a
    segment shared anywhere in either recording is found."""
    if a.size < AUDIO_BLOCK or b.size < AUDIO_BLOCK:
        return None
    probe, target, sign = (a, b, 1) if a.size <= b.size else (b, a, -1)
    windows = np.lib.stride_tricks.sliding_window_view(target, AUDIO_BLOCK)  # (positions, block)
    best: tuple[float, int] | None = None
    for start in list(range(0, probe.size - AUDIO_BLOCK + 1, AUDIO_BLOCK // 4))[:48]:
        block = probe[start:start + AUDIO_BLOCK]
        errors = np.bitwise_count(windows ^ block[None, :]).sum(axis=1) / (32 * AUDIO_BLOCK)
        j = int(np.argmin(errors))
        if best is None or errors[j] < best[0]:
            best = (float(errors[j]), sign * (j - start))
    return best
