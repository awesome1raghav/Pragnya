"""Pinned, offline SigLIP 2 visual embeddings; no model downloads on API requests."""

import hashlib
import io
import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MODEL_ID = "google/siglip2-base-patch16-224"
REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"
DIMENSIONS = 768
MODEL_KEY = f"siglip2-b16-224:{REVISION}:rgb-exif-v1"
MAX_PIXELS = 24_000_000


def decode_image(data: bytes, crop: list[int] | None = None) -> Image.Image:
    """Bound decoding, orient then crop. Screenshots are ordinary raster images.

    A crop uses [left, top, right, bottom] in oriented-image pixels. Never modifies evidence.
    Animated files are rejected rather than silently searching an arbitrary frame.
    """
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Use a JPEG, PNG or WebP image / video screenshot")
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("Image exceeds the 24 megapixel search limit")
            if getattr(source, "n_frames", 1) != 1:
                raise ValueError("Select a single frame or screenshot")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid or unsupported image") from exc
    if crop is not None:
        if (not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop)
                or not 0 <= crop[0] < crop[2] <= image.width
                or not 0 <= crop[1] < crop[3] <= image.height):
            raise ValueError("Crop must be an integer rectangle inside the oriented image")
        image = image.crop(tuple(crop))
    return image


def normalized(vector) -> list[float]:
    arr = np.asarray(vector, dtype=np.float32)
    if arr.shape != (DIMENSIONS,) or not np.isfinite(arr).all():
        raise ValueError("Invalid embedding dimensions or non-finite values")
    norm = float(np.linalg.norm(arr))
    if norm < 1e-8:
        raise ValueError("Zero embedding")
    return (arr / norm).tolist()


class ImageEncoder:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._model = None
        self._processor = None

    @property
    def ready(self) -> bool:
        return all((self.path / name).is_file() for name in
                   ("model.safetensors", "config.json", "preprocessor_config.json", "manifest.json"))

    def _load(self):
        if self._model is not None:
            return
        if not self.ready:
            raise RuntimeError("Install the pinned SigLIP 2 model with Scripts.Maintenance.InstallVisualModel")
        manifest = json.loads((self.path / "manifest.json").read_text())
        if manifest.get("revision") != REVISION:
            raise RuntimeError("Visual model revision does not match the index")
        for name in ("model.safetensors", "config.json", "preprocessor_config.json"):
            with (self.path / name).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != manifest.get("sha256", {}).get(name):
                raise RuntimeError("Visual model checksum mismatch")
        import torch
        from transformers import AutoImageProcessor, SiglipVisionModel

        torch.set_num_threads(min(4, torch.get_num_threads()))
        self._processor = AutoImageProcessor.from_pretrained(self.path, local_files_only=True, trust_remote_code=False)
        self._model = SiglipVisionModel.from_pretrained(
            self.path, local_files_only=True, use_safetensors=True, trust_remote_code=False,
        ).eval()

    def embed(self, images: list[Image.Image]) -> list[list[float]]:
        if not 1 <= len(images) <= 16:
            raise ValueError("Embedding batch must contain 1 to 16 images")
        # Serialise inference and cold loading to bound CPU/RAM on the local operator's laptop.
        with self._lock:
            self._load()
            import torch

            inputs = self._processor(images=images, return_tensors="pt")
            with torch.inference_mode():
                pooled = self._model(**inputs).pooler_output.float().cpu().numpy()
            return [normalized(row) for row in pooled]

    def from_file(self, path: Path, *, max_bytes: int = 10 * 1024 * 1024) -> list[float]:
        with Path(path).open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Image exceeds the search byte limit")
        return self.embed([decode_image(data)])[0]

    def from_url(self, url: str, *, max_bytes: int = 10 * 1024 * 1024) -> list[float]:
        from Backend.App.Modules.NexSrc.SafeFetch import fetch

        result = fetch(url, max_bytes=max_bytes, timeout=10)
        if result.status != 200:
            raise ValueError("Image URL did not return HTTP 200")
        return self.embed([decode_image(result.body or b"")])[0]
