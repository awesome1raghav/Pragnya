"""The detector host process with the real pinned models (skipped, with the reason, when Backend/Models is not
installed): scores flow back, a hung request is killed and the host recovers, a crashed host is restarted,
an unknown detector is "unavailable" rather than an error, and the engines report detector scores honestly."""

import uuid

import numpy as np
import pytest
from PIL import Image

from Backend.App.Config import get_settings
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion
from Backend.App.Detectors import Manifest
from Backend.App.Detectors.Host import DetectorFailed, DetectorHost, DetectorUnavailable
from Backend.App.Modules.NexAud import AudioAnalyzer
from Backend.App.Modules.NexImg import ImageAnalyzer

pytestmark = pytest.mark.skipif(
    not (Manifest.COMMUNITY_FORENSICS.path.is_file() and Manifest.SSL_AASIST_DF.path.is_file()),
    reason="detector weights are not installed (Backend/Models); see Documentation/Research/Detector Candidates.md",
)
SETTINGS = get_settings().model_copy(update={"DETECTORS_ENABLED": True})
EV = uuid.uuid4()


@pytest.fixture(scope="module")
def host():
    h = DetectorHost()
    yield h
    h.close()


@pytest.fixture(scope="module")
def photo(tmp_path_factory):
    rng = np.random.default_rng(2)
    path = tmp_path_factory.mktemp("photo") / "camera.png"
    Image.fromarray((np.linspace(40, 200, 512)[None, :, None] + rng.normal(0, 10, (384, 512, 3))).clip(0, 255).astype(np.uint8)).save(path)
    return path


def test_host_scores_and_reports_what_it_ran(host, photo):
    info = host.info("CommunityForensics")
    assert info.name == "CommunityForensics-ViT-S16-384" and info.version == Manifest.COMMUNITY_FORENSICS.sha256[:12] and info.licence == "MIT"
    score, seconds = host.score("CommunityForensics", photo, timeout=60)
    assert 0.0 <= score <= 1.0 and seconds > 0


def test_a_hung_request_is_killed_and_the_host_recovers(host, photo):
    with pytest.raises(DetectorFailed, match="did not answer"):
        host.score("CommunityForensics", photo, timeout=0.001)
    host._info.clear()  # the new child must load the model again
    assert 0.0 <= host.score("CommunityForensics", photo, timeout=120)[0] <= 1.0


def test_a_crashed_host_is_restarted(host, photo):
    host.score("CommunityForensics", photo, timeout=120)
    host._process.kill()
    host._process.wait()
    assert 0.0 <= host.score("CommunityForensics", photo, timeout=120)[0] <= 1.0


def test_an_unknown_detector_is_unavailable(host):
    with pytest.raises(DetectorUnavailable, match="unknown detector"):
        host.info("NoSuchDetector")


def test_image_engine_reports_the_detector_as_an_inference(photo):
    out = ImageAnalyzer.analyze(photo, EV, settings=SETTINGS)
    assert out.status is ExecutionState.COMPLETED and out.reason is None
    f = next(x for x in out.findings if x.finding_type == "SYNTHETIC_IMAGE_DETECTOR")
    assert f.assertion is Assertion.INFERENCE and f.confidence is None and f.score_kind.value == "METHOD_SPECIFIC"
    assert "not a probability" in f.description and any(limit.startswith("Measured locally: ROC AUC") for limit in f.limitations)
    assert f.measurement["detector_version"] == Manifest.COMMUNITY_FORENSICS.sha256[:12]


def test_image_engine_without_the_detector_says_why(photo):
    out = ImageAnalyzer.analyze(photo, EV, settings=SETTINGS.model_copy(update={"IMAGE_DETECTOR": "NoSuchDetector"}))
    assert (out.status, out.reason) == (ExecutionState.PARTIALLY_COMPLETED, "DETECTOR_NOT_INSTALLED")
    assert "SYNTHETIC_IMAGE_DETECTOR" not in {f.finding_type for f in out.findings}
    assert any("NoSuchDetector" in limit for limit in out.limitations)


def test_speech_engine_scores_windows_and_reports_the_highest(tmp_path):
    import wave

    rate = 16000
    t = np.arange(rate * 12) / rate
    signal = 0.2 * np.sin(2 * np.pi * 180 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t)) + 0.01 * np.random.default_rng(3).normal(size=t.size)
    path = tmp_path / "talk.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((signal * 32767).astype("<i2").tobytes())
    out = AudioAnalyzer.analyze(path, EV, settings=SETTINGS)
    assert out.status is ExecutionState.COMPLETED
    f = next(x for x in out.findings if x.finding_type == "SYNTHETIC_SPEECH_DETECTOR")
    windows = f.measurement["windows"]
    assert len(windows) == 3 and [w["start_s"] for w in windows] == [0.0, 3.981, 7.963]
    assert f.score == max(w["score"] for w in windows) and f.time_range.end_seconds - f.time_range.start_seconds == pytest.approx(4.0375, abs=0.01)
