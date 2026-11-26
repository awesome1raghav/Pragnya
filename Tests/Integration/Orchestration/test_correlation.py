"""Step 6 on a ground-truth set built here ("done when": offsets, trims and splices recovered within stated tolerance).

base      8 slides of distinct procedural photos (1 s each) with distinct noise bursts as audio
trimmed   base from 3.0 s on                → ALN offset -3.0 s (video ±0.5, audio ±0.05); TRN TRIMMED
dubbed    base pictures with other audio    → TRN AUDIO_REPLACED
spliced   one continuous scene, cut at 4.0 s to another scene and sound → CMC COINCIDENT_DISCONTINUITY near 4.0 s
"""

import subprocess

import numpy as np
import pytest
from PIL import Image

from Backend.App.Utils.MediaProbe import resolve_executable
from Tests.Integration.Orchestration.test_sources_lineage import drain
from Tests.Integration.Orchestration.test_tmir import API, api, fresh, new_case, upload  # noqa: F401 — fixtures

pytestmark = pytest.mark.postgres
FFMPEG = resolve_executable("ffmpeg")


def ff(*args):
    subprocess.run([FFMPEG, "-v", "error", "-y", *args], check=True, capture_output=True)


def photo(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:240, 0:320]
    f = rng.uniform(15, 60, 3)
    img = np.stack([128 + 90 * np.sin(x / f[0] + seed), 128 + 90 * np.cos(y / f[1] - seed), 128 + 80 * np.sin((x + y) / f[2])], axis=-1)
    for _ in range(4):
        x0, y0 = rng.integers(0, 260), rng.integers(0, 180)
        img[y0:y0 + 60, x0:x0 + 60] = rng.integers(0, 255, 3)
    return Image.fromarray((img + rng.normal(0, 5, img.shape)).clip(0, 255).astype("uint8"))


def noise_track(path, seed: int, seconds: float = 8.0, rate: int = 16000):
    import wave

    rng = np.random.default_rng(seed)
    bursts = [rng.normal(0, 1, int(rate * 0.25)) * rng.uniform(0.05, 0.4) for _ in range(int(seconds * 4))]
    filt = [np.convolve(b, np.ones(rng.integers(1, 12)) / 6, mode="same") for b in bursts]
    signal = np.concatenate(filt)[: int(seconds * rate)].clip(-1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((signal * 32767).astype("<i2").tobytes())


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("correlation")
    for i in range(8):
        photo(i).save(d / f"s{i}.png")
    noise_track(d / "a1.wav", 1)
    noise_track(d / "a2.wav", 2)
    ff("-framerate", "1", "-i", str(d / "s%d.png"), "-i", str(d / "a1.wav"), "-vf", "fps=25,format=yuv420p", "-c:v", "libx264",
       "-c:a", "aac", "-shortest", str(d / "base.mp4"))
    ff("-ss", "3.0", "-i", str(d / "base.mp4"), "-c:v", "libx264", "-c:a", "aac", str(d / "trimmed.mp4"))
    ff("-i", str(d / "base.mp4"), "-i", str(d / "a2.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(d / "dubbed.mp4"))
    # one continuous scene (slow pan over a photo with steady noise), cut at 4.0 s to a different scene and sound
    photo(20).resize((640, 480)).save(d / "wide1.png")
    photo(30).resize((640, 480)).save(d / "wide2.png")
    ff("-loop", "1", "-t", "4", "-i", str(d / "wide1.png"), "-loop", "1", "-t", "4", "-i", str(d / "wide2.png"),
       "-f", "lavfi", "-t", "4", "-i", "anoisesrc=color=pink:amplitude=0.2:sample_rate=16000:seed=1",
       "-f", "lavfi", "-t", "4", "-i", "sine=frequency=880:sample_rate=16000",
       "-filter_complex", "[0:v]crop=320:240:'t*40':60,fps=25[v0];[1:v]crop=320:240:'t*40':120,fps=25[v1];[v0][2:a][v1][3:a]concat=n=2:v=1:a=1[v][a]",
       "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(d / "spliced.mp4"))
    return {name: (d / f"{name}.mp4").read_bytes() for name in ("base", "trimmed", "dubbed", "spliced")}


def run_findings(client, case_id, module):
    """Findings of `module` from the newest run of the case that has a result for it."""
    for job in client.get(f"{API}/cases/{case_id}/runs").json()["data"]:
        run = client.get(f"{API}/runs/{job['job_id']}").json()["data"]
        entry = next((e for e in run["plan"] if e["module_id"] == module and e["result_id"]), None)
        if entry:
            return client.get(f"{API}/analyses/{entry['result_id']}").json()["data"]["envelope"]["findings"]
    return []


def test_trim_offset_and_hypothesis_are_recovered(api, clips):
    case_id = new_case(api)
    base = upload(api, case_id, clips["base"], "base.mp4", "video/mp4")
    trimmed = upload(api, case_id, clips["trimmed"], "trimmed.mp4", "video/mp4")
    drain(api)
    alignment = [f for f in run_findings(api, case_id, "NEX-ALN") if f["finding_type"] == "ALIGNMENT"]
    assert len(alignment) == 1
    m = alignment[0]["measurement"]
    forward = m["evidence_a"] == base["evidence_id"]
    expected = -3.0 if forward else 3.0
    assert abs(m["video"]["offset_s"] - expected) <= 0.5 and abs(m["video"]["speed"] - 1) < 0.03
    assert m["audio"]["matched"] and abs(m["audio"]["offset_s"] - expected) <= 0.05, m["audio"]
    trims = [f for f in run_findings(api, case_id, "NEX-TRN") if f["finding_type"] == "TRIMMED"]
    assert trims and trims[0]["assertion"] == "INFERENCE" and set(trims[0]["evidence_ids"]) == {base["evidence_id"], trimmed["evidence_id"]}


def test_replaced_audio_is_hypothesised(api, clips):
    case_id = new_case(api)
    upload(api, case_id, clips["base"], "base.mp4", "video/mp4")
    upload(api, case_id, clips["dubbed"], "dubbed.mp4", "video/mp4")
    drain(api)
    kinds = {f["finding_type"] for f in run_findings(api, case_id, "NEX-TRN")}
    assert "AUDIO_REPLACED" in kinds and "TRIMMED" not in kinds


def test_a_splice_is_found_by_picture_and_sound_together(api, clips):
    case_id = new_case(api)
    upload(api, case_id, clips["spliced"], "spliced.mp4", "video/mp4")
    drain(api)
    coincident = [f for f in run_findings(api, case_id, "NEX-CMC") if f["finding_type"] == "COINCIDENT_DISCONTINUITY"]
    assert coincident, "no coincident discontinuity"
    assert any(abs(f["measurement"]["visual_s"] - 4.0) <= 0.5 and abs(f["measurement"]["audio_s"] - 4.0) <= 0.5 for f in coincident)
    assert all(f["assertion"] == "INFERENCE" for f in coincident)
