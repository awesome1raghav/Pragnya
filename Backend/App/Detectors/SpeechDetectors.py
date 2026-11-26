"""Synthetic-speech detector: SSL-AASIST (Tak et al., Odyssey 2022), wav2vec 2.0 XLS-R 300M + AASIST back-end.

The back-end is the authors' code (model.py at the pinned commit). Their front-end loads XLS-R through fairseq,
which does not install on this platform; the same network is built with Hugging Face's Wav2Vec2Model from the
XLS-R config, and the checkpoint's own fine-tuned front-end weights are mapped onto it name by name (every tensor
must map; nothing is left at its pretrained value). Input as in the authors' evaluation: 16 kHz mono, the first
64,600 samples (about 4 s), shorter clips repeated to that length. Output: the softmax probability of the
"spoof" class, a METHOD_SPECIFIC score (the model is not calibrated on NEXTRON's audio).
"""

import importlib.util
import re
import sys
import types

import numpy as np
import torch
from torch import nn

from Backend.App.Detectors import Manifest

torch.set_grad_enabled(False)
CUT = 64_600
RATE = 16_000

_FAIRSEQ_TO_HF = [  # fairseq wav2vec2 parameter names -> transformers Wav2Vec2Model names
    (r"^feature_extractor\.conv_layers\.(\d+)\.0\.", r"feature_extractor.conv_layers.\1.conv."),
    (r"^feature_extractor\.conv_layers\.(\d+)\.2\.1\.", r"feature_extractor.conv_layers.\1.layer_norm."),
    (r"^post_extract_proj\.", "feature_projection.projection."),
    (r"^layer_norm\.", "feature_projection.layer_norm."),
    (r"^mask_emb$", "masked_spec_embed"),
    (r"^encoder\.pos_conv\.0\.weight_g$", "encoder.pos_conv_embed.conv.parametrizations.weight.original0"),
    (r"^encoder\.pos_conv\.0\.weight_v$", "encoder.pos_conv_embed.conv.parametrizations.weight.original1"),
    (r"^encoder\.pos_conv\.0\.bias$", "encoder.pos_conv_embed.conv.bias"),
    (r"^encoder\.layers\.(\d+)\.self_attn\.", r"encoder.layers.\1.attention."),
    (r"^encoder\.layers\.(\d+)\.self_attn_layer_norm\.", r"encoder.layers.\1.layer_norm."),
    (r"^encoder\.layers\.(\d+)\.fc1\.", r"encoder.layers.\1.feed_forward.intermediate_dense."),
    (r"^encoder\.layers\.(\d+)\.fc2\.", r"encoder.layers.\1.feed_forward.output_dense."),
    (r"^encoder\.layers\.(\d+)\.final_layer_norm\.", r"encoder.layers.\1.final_layer_norm."),
    (r"^encoder\.layer_norm\.", "encoder.layer_norm."),
]
_UNUSED = ("quantizer.", "project_q.", "final_proj.")  # pre-training heads, not part of the feature path


def _hf_name(name: str) -> str | None:
    if name.startswith(_UNUSED):
        return None
    for pattern, replacement in _FAIRSEQ_TO_HF:
        if re.match(pattern, name):
            return re.sub(pattern, replacement, name)
    raise KeyError(f"no mapping for front-end parameter {name}")


class _XlsrFrontEnd(nn.Module):
    """Stands in for the authors' SSLModel: same interface (`out_dim`, `extract_feat`)."""

    def __init__(self, device=None):
        super().__init__()
        from transformers import Wav2Vec2Config, Wav2Vec2Model

        config = Wav2Vec2Config.from_json_file(str(Manifest.verify(Manifest.XLSR_CONFIG)))
        config.apply_spec_augment = False
        self.model = Wav2Vec2Model(config)
        self.out_dim = 1024

    def extract_feat(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim == 3:
            x = x[:, :, 0]
        return self.model(x).last_hidden_state


def _load_authors_model_module():
    code = Manifest.verify_code(Manifest.SSL_AASIST_CODE)
    sys.modules.setdefault("fairseq", types.ModuleType("fairseq"))  # imported at the top of model.py; only SSLModel used it
    spec = importlib.util.spec_from_file_location("ssl_aasist_model", code / "model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SSLModel = _XlsrFrontEnd
    return module


class SslAasist:
    licence = "MIT (code), Apache-2.0 (XLS-R)"
    trained_on = "ASVspoof 2019 LA (bona fide speech and 2019-era TTS/VC attacks)"

    def __init__(self, variant: str = "DF") -> None:
        pinned = {"LA": Manifest.SSL_AASIST_LA, "DF": Manifest.SSL_AASIST_DF}[variant]
        self.name, self.version = f"SSL-AASIST-{variant}", pinned.sha256[:12]
        module = _load_authors_model_module()
        model = module.Model(None, "cpu")
        state = torch.load(Manifest.verify(pinned), map_location="cpu", weights_only=True)
        state = {k.removeprefix("module."): v for k, v in state.items()}
        mapped = {}
        for k, v in state.items():
            if k.startswith("ssl_model.model."):
                target = _hf_name(k.removeprefix("ssl_model.model."))
                if target is None:
                    continue
                mapped["ssl_model.model." + target] = v
            else:
                mapped[k] = v
        model.load_state_dict(mapped, strict=True)
        self.model = model.eval()

    @staticmethod
    def prepare(samples: np.ndarray) -> np.ndarray:
        """The authors' `pad`: the first CUT samples, or the clip repeated to that length."""
        if samples.size >= CUT:
            return samples[:CUT]
        repeats = CUT // max(samples.size, 1) + 1
        return np.tile(samples, repeats)[:CUT]

    def score_samples(self, samples_16k: np.ndarray) -> float:
        x = torch.from_numpy(self.prepare(samples_16k.astype(np.float32))).unsqueeze(0)
        logits = self.model(x)
        return float(torch.softmax(logits, dim=1)[0, 0])  # class 0 = spoof, class 1 = bona fide (authors' labels)
