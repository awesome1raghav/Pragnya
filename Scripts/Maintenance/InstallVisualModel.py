"""Explicit one-time model installation (about 1.5 GB download); requests never download weights."""

import hashlib
import json

from Backend.App.Config import get_settings
from Backend.App.Modules.NexFpm.Embeddings import MODEL_ID, REVISION


def main():
    from huggingface_hub import snapshot_download

    path = get_settings().VISUAL_MODEL_PATH
    files = ["config.json", "preprocessor_config.json", "model.safetensors"]
    snapshot_download(MODEL_ID, revision=REVISION, local_dir=path, allow_patterns=files)
    hashes = {}
    for name in files:
        with (path / name).open("rb") as stream:
            hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (path / "manifest.json").write_text(json.dumps({"model_id": MODEL_ID, "revision": REVISION, "sha256": hashes}, indent=2))
    print(f"Pinned visual model installed: {path}")


if __name__ == "__main__":
    main()
