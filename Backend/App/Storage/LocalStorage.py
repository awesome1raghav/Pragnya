"""Protected local filesystem storage for evidence originals, derived artifacts and upload staging."""

import os
import shutil
import stat
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from Backend.App.Storage.StorageInterface import DERIVED_KEY, ORIGINAL_KEY, StagingFile, StorageError, StorageHealth

ORIGINALS = "Originals"
DERIVED = "Derived"
STAGING = "Temporary"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._originals = self.root / ORIGINALS
        self._staging = self.root / STAGING

    def ensure_layout(self) -> None:
        self._originals.mkdir(parents=True, exist_ok=True)
        self._staging.mkdir(parents=True, exist_ok=True)

    # --- keys -----------------------------------------------------------------------------
    def _path_for(self, key: str) -> Path:
        if not ORIGINAL_KEY.fullmatch(key):
            raise StorageError("Invalid storage key")
        path = (self.root / key).resolve()
        if self._originals not in path.parents:
            raise StorageError("Storage key escapes the originals directory")
        return path

    # --- staging --------------------------------------------------------------------------
    def new_staging_path(self) -> Path:
        self._staging.mkdir(parents=True, exist_ok=True)
        return self._staging / f"{uuid.uuid4().hex}.part"

    def discard_staging(self, path: Path) -> None:
        path = Path(path)
        if path.parent.resolve() != self._staging:
            raise StorageError("Refusing to delete outside staging")
        path.unlink(missing_ok=True)

    def iter_staging(self) -> Iterator[StagingFile]:
        if not self._staging.exists():
            return
        for path in self._staging.glob("*.part"):
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            yield StagingFile(path=path, modified_at=modified)

    # --- originals ------------------------------------------------------------------------
    def promote_original(self, staged: Path, key: str) -> None:
        destination = self._path_for(key)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise StorageError("An original already exists at this key; originals are never overwritten")
            # Same volume: an atomic rename. On Windows rename refuses an existing target as well.
            os.rename(staged, destination)
            os.chmod(destination, stat.S_IREAD)
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError(f"Could not promote staged upload: {type(exc).__name__}") from exc

    def remove_unreferenced_original(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def open_original(self, key: str) -> BinaryIO:
        try:
            return open(self._path_for(key), "rb")
        except FileNotFoundError as exc:
            raise StorageError("Original not found in storage") from exc

    def local_path(self, key: str) -> Path | None:
        return self._path_for(key)

    # --- derived artifacts ----------------------------------------------------------------
    def _derived_path(self, key: str) -> Path:
        if not DERIVED_KEY.fullmatch(key):
            raise StorageError("Invalid derived-artifact key")
        path = (self.root / key).resolve()
        if (self.root / DERIVED).resolve() not in path.parents:
            raise StorageError("Derived key escapes the derived directory")
        return path

    def write_derived(self, key: str, data: bytes) -> None:
        """Writes a derived artifact once (atomically, via a temporary name) and makes it read-only."""
        path = self._derived_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise StorageError("A derived artifact already exists at this key")
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(data)
            os.rename(temporary, path)
            os.chmod(path, stat.S_IREAD)
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError(f"Could not write derived artifact: {type(exc).__name__}") from exc

    def derived_path(self, key: str) -> Path:
        return self._derived_path(key)

    def iter_original_keys(self) -> Iterator[str]:
        if not self._originals.exists():
            return
        for case_dir in self._originals.iterdir():
            if case_dir.is_dir():
                for item in case_dir.iterdir():
                    if item.is_file():
                        yield f"{ORIGINALS}/{case_dir.name}/{item.name}"

    # --- health ---------------------------------------------------------------------------
    def health(self) -> StorageHealth:
        try:
            self.ensure_layout()
            probe = self._staging / f".probe-{uuid.uuid4().hex}"
            probe.write_bytes(b"nextron")
            probe.unlink()
            return StorageHealth(available=True, writable=True, free_bytes=shutil.disk_usage(self.root).free)
        except OSError as exc:
            return StorageHealth(available=self.root.exists(), writable=False, free_bytes=None, error=type(exc).__name__)
