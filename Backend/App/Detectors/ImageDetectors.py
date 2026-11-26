"""Synthetic-image detectors, reproducing each model's published inference path.

Both return the model's sigmoid output in [0, 1], higher meaning "more like the generated images it was trained
on". That number is the model's own score (METHOD_SPECIFIC), not a probability: neither model is calibrated on
the media NEXTRON receives.

  CommunityForensics  ViT-S/16 at 384 px (timm), Park & Owens, CVPR 2025. Eval transform as in the authors'
                      dataloader: resize shorter side to 440, centre crop 384, ImageNet normalisation.
  SPAI                spectral learning at the original resolution, Karageorgiou et al., CVPR 2025. The model
                      code is the authors' (pinned commit), imported with its two training-only dependencies
                      (CLIP backbone, attention-overlay export) stubbed out.
"""

import collections
import sys
import types

import numpy as np
import torch
from PIL import Image

from Backend.App.Detectors import Manifest

torch.set_grad_enabled(False)


def _rgb(path) -> Image.Image:
    with Image.open(path) as im:
        im.load()
        return im.convert("RGB")


class CommunityForensics:
    name, version = "CommunityForensics-ViT-S16-384", Manifest.COMMUNITY_FORENSICS.sha256[:12]
    licence = "MIT"
    trained_on = "Community Forensics: 4,800+ generators (Park & Owens, CVPR 2025)"

    def __init__(self) -> None:
        import timm
        from safetensors.torch import load_file
        from torchvision import transforms

        model = timm.create_model("vit_small_patch16_384.augreg_in21k_ft_in1k", pretrained=False)
        model.head = torch.nn.Linear(384, 1)
        state = load_file(str(Manifest.verify(Manifest.COMMUNITY_FORENSICS)))
        state = {k.removeprefix("vit."): v for k, v in state.items()}
        model.load_state_dict(state, strict=True)
        self.model = model.eval()
        self.transform = transforms.Compose([
            transforms.Resize(440), transforms.CenterCrop(384), transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def score(self, path) -> float:
        x = self.transform(_rgb(path)).unsqueeze(0)
        return float(torch.sigmoid(self.model(x))[0, 0])


class Spai:
    name, version = "SPAI", Manifest.SPAI.sha256[:12]
    licence = "Apache-2.0"
    trained_on = "Latent-diffusion images (DMID LDM) with COCO/LSUN real images (Karageorgiou et al., CVPR 2025)"

    def __init__(self) -> None:
        code = Manifest.verify_code(Manifest.SPAI_CODE)
        # training-only imports of sid.py, not used by inference: the CLIP backbone and the attention-overlay export
        sys.modules.setdefault("clip", types.ModuleType("clip"))
        spai_utils = types.ModuleType("spai.utils")
        spai_utils.save_image_with_attention_overlay = lambda *a, **k: None
        sys.modules["spai.utils"] = spai_utils
        if str(code) not in sys.path:
            sys.path.insert(0, str(code))
        from spai.config import get_custom_config  # noqa: E402 — the authors' code at the pinned commit
        from spai.models.sid import build_mf_vit  # noqa: E402

        self.config = get_custom_config(str(code / "configs" / "spai.yaml"))  # as the authors' `infer` command builds it
        torch.serialization.add_safe_globals([(collections.Counter, "yacs.config.CfgNode")])
        checkpoint = torch.load(Manifest.verify(Manifest.SPAI), map_location="cpu", weights_only=True)
        model = build_mf_vit(self.config)
        model.load_state_dict(checkpoint["model"], strict=True)
        self.model = model.eval()
        self.batch = int(self.config.MODEL.FEATURE_EXTRACTION_BATCH)

    def score(self, path) -> float:
        array = np.asarray(_rgb(path), dtype=np.float32) / 255.0  # "positive_0_1" normalisation, original resolution
        x = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).contiguous()
        return float(torch.sigmoid(self.model([x], self.batch))[0, 0])
