"""NEX-EVD owns SHA-256 for evidence. Other modules reuse these digests; none re-implement them."""

import hashlib
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024
ALGORITHM = "SHA-256"


class StreamingDigest:
    """SHA-256 and byte count over data seen in order (used while an upload streams in)."""

    def __init__(self) -> None:
        self._hash = hashlib.sha256()
        self.size = 0

    def update(self, data: bytes) -> None:
        self._hash.update(data)
        self.size += len(data)

    @property
    def hexdigest(self) -> str:
        return self._hash.hexdigest()


def digest_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = StreamingDigest()
    while chunk := stream.read(CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest, digest.size


def digest_file(path: Path) -> tuple[str, int]:
    with open(path, "rb") as stream:
        return digest_stream(stream)
