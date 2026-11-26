"""Step 4 media engines on controlled fixtures (archive acceptance: genuine, manipulated and benignly compressed
examples; absent audio; signed, modified, missing and unsupported credentials). Each fixture is generated here,
so the expected answer is known by construction. No database is needed."""

import datetime
import io
import json
import shutil
import subprocess
import uuid
import wave

import c2pa
import numpy as np
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from PIL import Image

from Backend.App.Config import get_settings
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Modules.NexAud import AudioAnalyzer
from Backend.App.Modules.NexImg import ImageAnalyzer
from Backend.App.Modules.NexPrv import C2paAnalyzer
from Backend.App.Modules.NexVid import VideoAnalyzer

SETTINGS = get_settings()
FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="FFmpeg is required for video and audio fixtures")
EV = uuid.uuid4()


def kinds(out):
    return [f.finding_type for f in out.findings]


def one(out, kind):
    found = [f for f in out.findings if f.finding_type == kind]
    assert len(found) == 1, kinds(out)
    return found[0]


def ffmpeg(*args):
    subprocess.run([FFMPEG, "-v", "error", "-y", *args], check=True, capture_output=True)


# ── NEX-IMG ──────────────────────────────────────────────────────────────────────────────────

def _photo(seed=1, h=300, w=400):
    rng = np.random.default_rng(seed)
    base = np.linspace(60, 190, w)[None, :, None] + np.linspace(-20, 20, h)[:, None, None]
    return (base + rng.normal(0, 12, (h, w, 3))).clip(0, 255).astype(np.uint8)


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    d = tmp_path_factory.mktemp("img")
    genuine = _photo()
    Image.fromarray(genuine).save(d / "genuine.jpg", quality=92)
    spliced = genuine.copy()
    # paste a block from a much cleaner source (sensor noise std 1.5 instead of 12)
    spliced[100:180, 160:260] = np.clip(150 + np.random.default_rng(3).normal(0, 1.5, (80, 100, 3)), 0, 255).astype(np.uint8)
    Image.fromarray(spliced).save(d / "spliced.jpg", quality=92)
    Image.open(d / "genuine.jpg").save(d / "recompressed.jpg", quality=70)  # benign: a second, harsher compression
    Image.fromarray(genuine).save(d / "genuine.png")
    Image.fromarray(_photo(seed=4, h=200, w=260)).resize((390, 300), Image.Resampling.BILINEAR).save(d / "upscaled.png")  # 1.5x
    return d


def test_image_genuine_has_no_localised_response(images):
    out = ImageAnalyzer.analyze(images / "genuine.jpg", EV)
    assert out.status is ExecutionState.PARTIALLY_COMPLETED and out.reason == "DETECTOR_NOT_INSTALLED"
    assert "NOISE_LEVEL_CONSISTENT" in kinds(out) and "ELA_UNIFORM_RESPONSE" in kinds(out)
    assert one(out, "JPEG_QUANTIZATION").measurement["estimated_ijg_quality"] == 92
    assert all(f.confidence is None for f in out.findings)
    assert any("detector" in limit for limit in out.limitations)


def test_image_splice_is_localised_where_it_was_pasted(images):
    out = ImageAnalyzer.analyze(images / "spliced.jpg", EV)
    f = one(out, "NOISE_LEVEL_INCONSISTENCY")
    reg = f.region  # the pasted block spans x 40–65 %, y 33–60 %
    assert reg.x <= 45 and reg.x + reg.w >= 60 and reg.y <= 38 and reg.y + reg.h >= 55
    assert reg.w < 50 and reg.h < 50  # a region, not the whole image
    assert f.supporting_artifact_ids and f.supporting_artifact_ids[0] in {a.artifact_id for a in out.artifacts}


def test_image_benign_recompression_is_reported_without_a_false_region(images):
    out = ImageAnalyzer.analyze(images / "recompressed.jpg", EV)
    assert "NOISE_LEVEL_INCONSISTENCY" not in kinds(out) and "ELA_LOCAL_RESPONSE" not in kinds(out)
    assert one(out, "JPEG_QUANTIZATION").measurement["estimated_ijg_quality"] == 70


def test_image_resizing_leaves_interpolation_traces(images):
    resized = one(ImageAnalyzer.analyze(images / "upscaled.png", EV), "RESAMPLING_TRACES")
    assert resized.measurement["horizontal"]["peak_frequency_cycles_per_px"] == pytest.approx(1 / 3, abs=0.01)  # 1.5x aliases to 1/3
    assert "NO_RESAMPLING_TRACES" in kinds(ImageAnalyzer.analyze(images / "genuine.png", EV))


def test_image_results_are_deterministic(images):
    a, b = (ImageAnalyzer.analyze(images / "spliced.jpg", EV) for _ in range(2))
    strip = lambda o: [(f.finding_type, f.score, f.region, json.dumps(f.measurement, sort_keys=True)) for f in o.findings]  # noqa: E731
    assert strip(a) == strip(b)
    assert [x.data for x in a.artifacts] == [x.data for x in b.artifacts]
    assert one(a, "PERCEPTUAL_HASHES").measurement["phash"] == one(b, "PERCEPTUAL_HASHES").measurement["phash"]


def test_image_decompression_bomb_is_refused(tmp_path):
    Image.new("L", (10_000, 9_000)).save(tmp_path / "huge.png")
    with pytest.raises(ValueError, match="limit"):
        ImageAnalyzer.analyze(tmp_path / "huge.png", EV)


# ── NEX-VID ──────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    if FFMPEG is None:
        pytest.skip("FFmpeg is required")
    d = tmp_path_factory.mktemp("vid")
    # a hard cut at 2.0 s between two unrelated scenes, with audio
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i", "smptebars=size=320x240:rate=25:duration=2",
           "-f", "lavfi", "-i", "sine=frequency=330:duration=4:sample_rate=44100",
           "-filter_complex", "[1:v]trim=duration=2,setpts=PTS-STARTPTS[b];[0:v][b]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "25", "-c:a", "aac", "-shortest", str(d / "cut.mp4"))
    # a clip with the frames from 1.5 s to 3.5 s removed (timestamps kept), and no audio stream
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=5", "-vf", "select='not(between(t,1.5,3.5))'",
           "-fps_mode", "passthrough", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(d / "gap.mp4"))
    return d


@needs_ffmpeg
def test_video_hard_cut_is_found_at_its_time(videos):
    out = VideoAnalyzer.analyze(videos / "cut.mp4", EV, settings=SETTINGS)
    assert out.status is ExecutionState.PARTIALLY_COMPLETED and out.reason == "DETECTOR_NOT_INSTALLED"
    cuts = [f for f in out.findings if f.finding_type == "VISUAL_DISCONTINUITY"]
    assert any(abs(f.time_range.end_seconds - 2.0) <= 0.26 for f in cuts), [(f.time_range, f.score) for f in cuts]
    timing = one(out, "FRAME_TIMING").measurement
    assert timing["nominal_fps"] == pytest.approx(25, abs=0.1) and timing["gaps"] == 0
    assert {a.kind.value for a in out.artifacts} == {"FRAME_SET", "FINGERPRINT"}


@needs_ffmpeg
def test_video_timestamp_gap_is_located(videos):
    out = VideoAnalyzer.analyze(videos / "gap.mp4", EV, settings=SETTINGS)
    gaps = [f for f in out.findings if f.finding_type == "TIMESTAMP_GAP"]
    assert len(gaps) == 1 and gaps[0].time_range.start_seconds == pytest.approx(1.48, abs=0.05)
    assert gaps[0].measurement["gap_s"] == pytest.approx(2.04, abs=0.05)


@needs_ffmpeg
def test_video_frame_time_mapping_is_reproducible(videos):
    a, b = (VideoAnalyzer.analyze(videos / "cut.mp4", EV, settings=SETTINGS) for _ in range(2))
    sig = lambda o: next(x for x in o.artifacts if x.kind.value == "FINGERPRINT").data  # noqa: E731
    assert sig(a) == sig(b)
    frames = json.loads(sig(a))["frames"]
    assert [f["t"] for f in frames[:4]] == [0.0, 0.25, 0.5, 0.75]


# ── NEX-AUD ──────────────────────────────────────────────────────────────────────────────────

def _wav(path, samples, rate):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


@pytest.fixture(scope="module")
def sounds(tmp_path_factory):
    d = tmp_path_factory.mktemp("aud")
    rate = 44100
    t = np.arange(int(rate * 4)) / rate
    rng = np.random.default_rng(5)
    room = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.02 * rng.normal(size=t.size)
    _wav(d / "continuous.wav", room, rate)
    edited = room.copy()
    edited[int(1.0 * rate):int(1.2 * rate)] = 0.0                                   # digital silence 1.0–1.2 s
    edited[int(2.5 * rate):] = 0.3 * rng.normal(size=edited.size - int(2.5 * rate))  # replaced segment from 2.5 s
    _wav(d / "edited.wav", edited, rate)
    # band-limited: generated at 8 kHz and upsampled to 44.1 kHz
    low = 0.3 * np.sin(2 * np.pi * 300 * np.arange(8000 * 3) / 8000) + 0.05 * rng.normal(size=8000 * 3)
    _wav(d / "narrow8k.wav", low, 8000)
    if FFMPEG:
        ffmpeg("-i", str(d / "narrow8k.wav"), "-ar", "44100", str(d / "upsampled.wav"))
    return d


@needs_ffmpeg
def test_audio_edits_are_located(sounds):
    out = AudioAnalyzer.analyze(sounds / "edited.wav", EV, settings=SETTINGS)
    assert out.status is ExecutionState.PARTIALLY_COMPLETED
    silence = one(out, "DIGITAL_SILENCE")
    assert silence.time_range.start_seconds == pytest.approx(1.0, abs=0.01) and silence.measurement["length_s"] == pytest.approx(0.2, abs=0.01)
    changes = [f.time_range for f in out.findings if f.finding_type == "SPECTRAL_DISCONTINUITY"]
    assert any(abs(tr.start_seconds - 2.5) < 0.05 for tr in changes), changes
    assert {a.kind.value for a in out.artifacts} == {"HEATMAP", "AUDIO_TRACK"}
    with wave.open(io.BytesIO(next(a.data for a in out.artifacts if a.kind.value == "AUDIO_TRACK"))) as w:
        assert (w.getframerate(), w.getnchannels()) == (16000, 1) and w.getnframes() == pytest.approx(4 * 16000, abs=2)


@needs_ffmpeg
def test_audio_continuous_recording_has_no_edit_candidates(sounds):
    out = AudioAnalyzer.analyze(sounds / "continuous.wav", EV, settings=SETTINGS)
    assert "DIGITAL_SILENCE" not in kinds(out) and "SPECTRAL_DISCONTINUITY" not in kinds(out)
    assert one(out, "AUDIO_LEVELS").measurement["native_sample_rate_hz"] == 44100


@needs_ffmpeg
def test_audio_upsampling_shows_in_the_bandwidth(sounds):
    narrow = one(AudioAnalyzer.analyze(sounds / "upsampled.wav", EV, settings=SETTINGS), "EFFECTIVE_BANDWIDTH").measurement
    full = one(AudioAnalyzer.analyze(sounds / "edited.wav", EV, settings=SETTINGS), "EFFECTIVE_BANDWIDTH").measurement
    assert narrow["bandwidth_99_hz"] <= 4000 < full["bandwidth_99_hz"]


@needs_ffmpeg
def test_audio_module_reports_absent_audio_itself(videos):
    out = AudioAnalyzer.analyze(videos / "gap.mp4", EV, settings=SETTINGS)
    assert (out.status, out.reason) == (ExecutionState.SKIPPED, "NOT_APPLICABLE") and out.findings == []


@needs_ffmpeg
def test_audio_without_chromaprint_says_so(sounds):
    settings = SETTINGS.model_copy(update={"FPCALC_PATH": "definitely-not-fpcalc"})
    out = AudioAnalyzer.analyze(sounds / "continuous.wav", EV, settings=settings)
    assert any("Chromaprint" in limit for limit in out.limitations) and "ACOUSTIC_FINGERPRINT" not in kinds(out)


# ── NEX-PRV ──────────────────────────────────────────────────────────────────────────────────

def _signer():
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key, key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NEXTRON Test Root"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEXTRON tests")])
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NEXTRON Test Signer"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEXTRON tests")])
    valid = dict(not_valid_before=now - datetime.timedelta(days=1), not_valid_after=now + datetime.timedelta(days=30))
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(1)
          .not_valid_before(valid["not_valid_before"]).not_valid_after(valid["not_valid_after"])
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True).sign(ca_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name).public_key(key.public_key()).serial_number(2)
            .not_valid_before(valid["not_valid_before"]).not_valid_after(valid["not_valid_after"])
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False).sign(ca_key, hashes.SHA256()))
    chain = leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return c2pa.Signer.from_info(c2pa.C2paSignerInfo(b"es256", chain, pem, None))


@pytest.fixture(scope="module")
def credentials(tmp_path_factory):
    d = tmp_path_factory.mktemp("prv")
    buf = io.BytesIO()
    Image.fromarray(_photo()).save(buf, "JPEG", quality=90)
    (d / "plain.jpg").write_bytes(buf.getvalue())
    manifest = {"claim_generator_info": [{"name": "nextron-tests", "version": "1"}], "title": "signed.jpg",
                "assertions": [{"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created",
                                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"}]}}]}
    signed = io.BytesIO()
    c2pa.Builder(json.dumps(manifest)).sign(_signer(), "image/jpeg", io.BytesIO(buf.getvalue()), signed)
    (d / "signed.jpg").write_bytes(signed.getvalue())
    tampered = bytearray(signed.getvalue())
    tampered[-200] ^= 0xFF  # change image data after signing
    (d / "tampered.jpg").write_bytes(bytes(tampered))
    return d


def test_provenance_absent_credentials_are_not_evidence_of_anything(credentials):
    out = C2paAnalyzer.analyze(credentials / "plain.jpg", EV, mime_type="image/jpeg")
    f = one(out, "NO_CONTENT_CREDENTIALS")
    assert out.status is ExecutionState.COMPLETED and f.measurement == {"state": "ABSENT"}
    assert "not evidence of manipulation" in f.limitations[0]


def test_provenance_valid_signature_from_an_untrusted_signer(credentials):
    f = one(C2paAnalyzer.analyze(credentials / "signed.jpg", EV, mime_type="image/jpeg"), "CONTENT_CREDENTIALS_VALID")
    m = f.measurement
    assert (m["state"], m["signer"], m["algorithm"]) == ("VALID", "NEXTRON Test Signer", "Es256")
    assert m["actions"][0]["action"] == "c2pa.created" and "signingCredential.untrusted" in {x["code"] for x in m["failures"]}
    assert "not on a trust list" in f.title and any("do not prove the content is true" in limit for limit in f.limitations)


def test_provenance_modified_after_signing_is_invalid(credentials):
    f = one(C2paAnalyzer.analyze(credentials / "tampered.jpg", EV, mime_type="image/jpeg"), "CONTENT_CREDENTIALS_INVALID")
    assert f.measurement["state"] == "INVALID" and "assertion.dataHash.mismatch" in f.description


def test_provenance_unsupported_format_is_not_applicable(tmp_path):
    (tmp_path / "x.ogg").write_bytes(b"OggS" + bytes(200))
    out = C2paAnalyzer.analyze(tmp_path / "x.ogg", EV, mime_type="audio/ogg")
    assert (out.status, out.reason) == (ExecutionState.SKIPPED, "NOT_APPLICABLE")
