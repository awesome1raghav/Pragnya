"""Detector integrity guard and the fairseq → transformers weight mapping. Tests that need the downloaded weights
(Backend/Models, git-ignored) say so and are skipped when the weights are not installed on this machine."""

import hashlib

import pytest

pytest.importorskip("torch", reason="the detectors extra (PyTorch) is not installed, e.g. in the lean Docker image")

from Backend.App.Detectors import Manifest  # noqa: E402
from Backend.App.Detectors.SpeechDetectors import _hf_name  # noqa: E402

weights = pytest.mark.skipif(not Manifest.COMMUNITY_FORENSICS.path.is_file(), reason="detector weights are not installed (Backend/Models)")


def test_a_file_with_a_different_digest_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(Manifest, "MODELS_ROOT", tmp_path)
    (tmp_path / "x.bin").write_bytes(b"genuine")
    good = Manifest.PinnedFile("x.bin", hashlib.sha256(b"genuine").hexdigest(), 7, "test", "MIT")
    assert Manifest.verify(good) == tmp_path / "x.bin"
    (tmp_path / "y.bin").write_bytes(b"tampered")
    with pytest.raises(Manifest.IntegrityError, match="does not match"):
        Manifest.verify(Manifest.PinnedFile("y.bin", hashlib.sha256(b"genuine").hexdigest(), 8, "test", "MIT"))
    with pytest.raises(Manifest.IntegrityError, match="not installed"):
        Manifest.verify(Manifest.PinnedFile("absent.bin", "0" * 64, 0, "test", "MIT"))


@pytest.mark.parametrize(("fairseq", "hf"), [
    ("feature_extractor.conv_layers.3.0.weight", "feature_extractor.conv_layers.3.conv.weight"),
    ("feature_extractor.conv_layers.3.2.1.bias", "feature_extractor.conv_layers.3.layer_norm.bias"),
    ("post_extract_proj.weight", "feature_projection.projection.weight"),
    ("layer_norm.weight", "feature_projection.layer_norm.weight"),
    ("encoder.pos_conv.0.weight_g", "encoder.pos_conv_embed.conv.parametrizations.weight.original0"),
    ("encoder.layers.23.self_attn.q_proj.weight", "encoder.layers.23.attention.q_proj.weight"),
    ("encoder.layers.7.fc2.bias", "encoder.layers.7.feed_forward.output_dense.bias"),
    ("encoder.layer_norm.bias", "encoder.layer_norm.bias"),
    ("quantizer.vars", None),
])
def test_xlsr_parameter_names_map_one_to_one(fairseq, hf):
    assert _hf_name(fairseq) == hf


def test_an_unknown_front_end_parameter_is_an_error():
    with pytest.raises(KeyError):
        _hf_name("encoder.something_new.weight")


@weights
def test_installed_weights_match_their_pins():
    for pinned in (Manifest.COMMUNITY_FORENSICS, Manifest.SPAI, Manifest.SSL_AASIST_DF, Manifest.SSL_AASIST_LA, Manifest.GEND):
        assert Manifest.verify(pinned).stat().st_size == pinned.size_bytes
    Manifest.verify_code(Manifest.SPAI_CODE)
    Manifest.verify_code(Manifest.SSL_AASIST_CODE)
