"""Pinned detector weights: the exact file, its SHA-256, where it came from and under which licence.

A detector refuses to load a file whose digest differs from the one recorded here. Weights live in
Backend/Models/ (git-ignored; see Documentation/Research/Detector Candidates.md for how they were obtained).
Pickle-format files are loaded only with torch.load(weights_only=True), which accepts tensors and plain data
and refuses to run code; SPAI's checkpoint stores its training configuration as a yacs CfgNode, which is mapped
onto collections.Counter (a plain dict) for that purpose only.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from Backend.App.Config import BACKEND_ROOT

MODELS_ROOT = BACKEND_ROOT / "Models"


@dataclass(frozen=True)
class PinnedFile:
    relative_path: str
    sha256: str
    size_bytes: int
    source: str
    licence: str

    @property
    def path(self) -> Path:
        return MODELS_ROOT / self.relative_path


@dataclass(frozen=True)
class PinnedCode:
    repository: str
    commit: str
    licence: str

    @property
    def path(self) -> Path:
        return MODELS_ROOT / "Source" / self.repository.replace("/", "__")


COMMUNITY_FORENSICS = PinnedFile(
    "CommunityForensics/model.safetensors", "b89f36275f3bf5e2b040eee36597a8f19db051bff9a473a9cf7b2466284fb387", 87_262_324,
    "https://huggingface.co/OwensLab/commfor-model-384", "MIT")
SPAI = PinnedFile(
    "SPAI/spai.pth", "24159f27d7c8c2cd0cb6c4019189eb89ad0874a0d9d15f8dc9afd39ca9648a55", 934_865_338,
    "https://drive.google.com/file/d/1vvXmZqs6TVJdj8iF1oJ4L_fcgdQrp_YI (linked from github.com/mever-team/spai)", "Apache-2.0")
SPAI_CODE = PinnedCode("mever-team/spai", "8ff7b3b6779b4fcb43cf313471d9cb1c62d129a4", "Apache-2.0")
SSL_AASIST_LA = PinnedFile(
    "SSL-AASIST/LA_model.pth", "bd6f36097259fe54e7004eb983651e5304d807be81156dbd04faccb70d91e10c", 1_271_633_441,
    "https://drive.google.com/drive/folders/1c4ywztEVlYVijfwbGLl9OEa1SNtFKppB (linked from github.com/TakHemlata/SSL_Anti-spoofing)", "MIT")
SSL_AASIST_DF = PinnedFile(
    "SSL-AASIST/Best_LA_model_for_DF.pth", "1cf904f1d84c867c278cd42161df5367939d61cc28bfefd239bc995af59c2804", 1_271_642_081,
    "https://drive.google.com/drive/folders/1c4ywztEVlYVijfwbGLl9OEa1SNtFKppB (linked from github.com/TakHemlata/SSL_Anti-spoofing)", "MIT")
SSL_AASIST_CODE = PinnedCode("TakHemlata/SSL_Anti-spoofing", "4acaa61dcef5f7610f43aa4d0b29c4559b970cd2", "MIT")
XLSR_CONFIG = PinnedFile(
    "XLSR300M/config.json", "0bffa0d0e98153e883b828d86491f3c6062cb563dc9d7a9cfd1790da30c286ac", 1568,
    "https://huggingface.co/facebook/wav2vec2-xls-r-300m", "Apache-2.0")
GEND = PinnedFile(
    "GenD/model.ckpt", "57a0d00f2f5b4046afd2c344ff9877a35e8889e075916cf816796c54816c9955", 1_214_300_978,
    "https://huggingface.co/yermandy/deepfake-detection", "MIT")


class IntegrityError(RuntimeError):
    """A pinned file is missing or its bytes differ from the recorded digest."""


_VERIFIED: set[tuple] = set()  # (path, pinned digest, size, mtime): a file changed on disk is hashed again


def verify(pinned: PinnedFile) -> Path:
    path = pinned.path
    if not path.is_file():
        raise IntegrityError(f"{pinned.relative_path} is not installed (expected in {MODELS_ROOT})")
    stat = path.stat()
    key = (str(path.resolve()), pinned.sha256, stat.st_size, stat.st_mtime_ns)
    if key in _VERIFIED:
        return path
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            digest.update(chunk)
    if digest.hexdigest() != pinned.sha256:
        raise IntegrityError(f"{pinned.relative_path} does not match its pinned SHA-256; refusing to load it")
    _VERIFIED.add(key)
    return path


def verify_code(code: PinnedCode) -> Path:
    import subprocess

    head = subprocess.run(["git", "-C", str(code.path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != code.commit:
        raise IntegrityError(f"{code.repository} is at {head or 'nothing'}, not the pinned commit {code.commit}")
    dirty = subprocess.run(["git", "-C", str(code.path), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if dirty:
        raise IntegrityError(f"{code.repository} has local modifications; refusing to import it")
    return code.path
