"""The evidence storage contract. LocalStorage implements it now; an S3-compatible adapter can later.

Keys are built only from UUIDs by the application (never from client filenames):
    Originals/<case_id>/<evidence_id>
    Derived/<case_id>/<evidence_id>/<artifact_id>.<ext>     module outputs (heatmaps, frames, audio tracks)
Derived artifacts are written once and kept read-only, like originals; their SHA-256 is recorded with them.
"""

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol

ORIGINAL_KEY = re.compile(r"^Originals/[0-9a-f-]{36}/[0-9a-f-]{36}$")


DERIVED_KEY = re.compile(r"^Derived/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.(png|json|wav)$")


def original_key(case_id: uuid.UUID, evidence_id: uuid.UUID) -> str:
    return f"Originals/{case_id}/{evidence_id}"


def derived_key(case_id: uuid.UUID, evidence_id: uuid.UUID, artifact_id: uuid.UUID, extension: str) -> str:
    return f"Derived/{case_id}/{evidence_id}/{artifact_id}.{extension}"


class StorageError(Exception):
    """Storage could not complete an operation; the caller must not report success."""


@dataclass(frozen=True)
class StagingFile:
    path: Path
    modified_at: datetime


@dataclass(frozen=True)
class StorageHealth:
    available: bool
    writable: bool
    free_bytes: int | None
    error: str | None = None


class EvidenceStorage(Protocol):
    def new_staging_path(self) -> Path:
        """A fresh, not-yet-existing staging file path for an incoming upload."""

    def discard_staging(self, path: Path) -> None: ...

    def promote_original(self, staged: Path, key: str) -> None:
        """Move staged bytes to an original key. Never overwrites; leaves the original read-only."""

    def remove_unreferenced_original(self, key: str) -> None:
        """Only for an original whose database record was never committed."""

    def exists(self, key: str) -> bool: ...

    def open_original(self, key: str) -> BinaryIO: ...

    def local_path(self, key: str) -> Path | None:
        """Filesystem path when the adapter is local (for ranged file responses), else None."""

    def iter_original_keys(self) -> Iterator[str]: ...

    def iter_staging(self) -> Iterator[StagingFile]: ...

    def health(self) -> StorageHealth: ...
