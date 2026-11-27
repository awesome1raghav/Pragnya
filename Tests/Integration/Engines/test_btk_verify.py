"""Controlled matches, negative controls, and inconclusive states for NEX-BTK."""
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image

from Backend.App.Modules.NexBtk.Verify import _speed, verify

CORPUS = Path(__file__).resolve().parents[2] / "QA-Audit" / "NEXTRON-QA-001"


def test_image_variants_and_flat_control(tmp_path):
    original = CORPUS / "IMG-01.jpg"
    resized = verify(original, CORPUS / "IMG-03.jpg", "IMAGE", "IMAGE", ffprobe="ffprobe", timeout=60)
    assert resized["status"] == "CANDIDATE_MATCH"
    assert resized["checks"]["image"]["transformation"] == "unaltered"
    flat = tmp_path / "flat.png"
    Image.new("L", (128, 128), 80).save(flat)
    assert verify(flat, flat, "IMAGE", "IMAGE", ffprobe="ffprobe", timeout=60)["status"] == "INCONCLUSIVE"
    rng = np.random.default_rng(41)
    image = Image.fromarray(rng.integers(0, 256, (220, 280), dtype=np.uint8))
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    image.save(a)
    image.rotate(90, expand=True).save(b)
    rotated = verify(a, b, "IMAGE", "IMAGE", ffprobe="ffprobe", timeout=60)
    assert rotated["status"] == "CANDIDATE_MATCH"
    assert rotated["checks"]["image"]["transformation"].startswith("rotate_")
    image.crop((35, 28, 245, 192)).save(b)
    cropped = verify(a, b, "IMAGE", "IMAGE", ffprobe="ffprobe", timeout=60)
    assert cropped["status"] == "CANDIDATE_MATCH"
    assert "crop" in cropped["checks"]["image"]["transformation"]
    Image.fromarray(rng.integers(0, 256, (220, 280), dtype=np.uint8)).save(b)
    assert verify(a, b, "IMAGE", "IMAGE", ffprobe="ffprobe", timeout=60)["status"] == "NO_VERIFIED_LOCAL_MATCH"


def test_audio_variant_and_unrelated_control():
    related = verify(CORPUS / "AUD-01.wav", CORPUS / "AUD-02.wav", "AUDIO", "AUDIO", ffprobe="ffprobe", timeout=60)
    unrelated = verify(CORPUS / "AUD-01.wav", CORPUS / "AUD-03.wav", "AUDIO", "AUDIO", ffprobe="ffprobe", timeout=60)
    assert related["status"] == "CANDIDATE_MATCH"
    assert unrelated["status"] == "NO_VERIFIED_LOCAL_MATCH"


def test_video_checks_and_negative_control():
    related = verify(CORPUS / "VID-01.mp4", CORPUS / "VID-03.mp4", "VIDEO", "VIDEO", ffprobe="ffprobe", timeout=60)
    unrelated = verify(CORPUS / "VID-01.mp4", CORPUS / "VID-04.mp4", "VIDEO", "VIDEO", ffprobe="ffprobe", timeout=60)
    assert related["checks"]["video"]["status"] == "CANDIDATE_MATCH"
    assert "speed" in related["checks"] and "audio" in related["checks"]
    assert unrelated["status"] != "CANDIDATE_MATCH"


def test_known_half_speed_transform(tmp_path):
    rng = np.random.default_rng(71)
    for i in range(12):
        Image.fromarray(rng.integers(0, 256, (16, 16), dtype=np.uint8)).resize(
            (320, 320), Image.Resampling.NEAREST).save(tmp_path / f"frame{i:02d}.png")
    original, faster = tmp_path / "original.mp4", tmp_path / "faster.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1", "-i", str(tmp_path / "frame%02d.png"),
                    "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(original)], check=True, timeout=30)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(original), "-filter:v", "setpts=0.5*PTS",
                    "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(faster)], check=True, timeout=30)
    result = _speed(original, faster, "ffprobe", 60)
    assert result["status"] == "CANDIDATE_MATCH"
    assert result["speed"] == .5
