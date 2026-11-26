"""Step 9 backup and restore drill on a disposable database: encrypted backup, restore into a new database and storage
root, verification by row counts and evidence SHA-256; wrong key, tampering, truncation and non-empty targets refused.
Uses pg_dump / pg_restore inside the Compose PostgreSQL container (PG_TOOLS, default docker:nextron-postgres)."""

import os
import shutil

import pytest

from Backend.App.Services import Backup
from Tests.Integration.Orchestration.test_tmir import API, api, fresh, new_case, upload  # noqa: F401 — fixtures

pytestmark = pytest.mark.postgres


@pytest.fixture()
def tools():
    mode = os.environ.get("PG_TOOLS", "docker:nextron-postgres")
    if mode == "local" and not shutil.which("pg_dump"):
        pytest.skip("PG_TOOLS=local but pg_dump is not on PATH")
    if mode.startswith("docker:") and not (shutil.which("docker") or os.path.exists(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")):
        pytest.skip("No PostgreSQL client tools: set PG_TOOLS=local or run Docker")


def test_backup_restores_to_a_verified_copy(api, fresh, media, database_factory, tmp_path, tools):
    case_id = new_case(api)
    upload(api, case_id, media["png"], "a.png", "image/png")
    upload(api, case_id, media["jpeg_exif"], "b.jpg", "image/jpeg")
    key = Backup.new_key()

    backup = Backup.create_backup(fresh[0], fresh[1], tmp_path / "Backups", key)
    m = backup.manifest
    assert len(m["evidence"]) == 2 and m["row_counts"]["evidence"] == 2 and m["alembic_head"]
    raw = (backup.path / "database.dump.enc").read_bytes()
    assert raw.startswith(b"NXBK1") and b"PGDMP" not in raw[:4096]  # encrypted, not a readable dump
    assert not list(backup.path.glob("*.dump")) and not list(backup.path.glob("*.tar"))  # no plaintext left behind

    _, target = database_factory()
    report = Backup.restore_backup(backup.path, key, target, tmp_path / "restored")
    assert report["ok"] and report["evidence_verified"] == 2 and report["rows"] == sum(m["row_counts"].values())

    with pytest.raises(Backup.BackupError, match="not empty"):  # never over existing data
        Backup.restore_backup(backup.path, key, target, tmp_path / "other")
    _, spare = database_factory()
    with pytest.raises(Backup.BackupError, match="failed authentication"):
        Backup.restore_backup(backup.path, Backup.new_key(), spare, tmp_path / "wrong-key")

    tampered = tmp_path / "tampered"
    shutil.copytree(backup.path, tampered)
    data = bytearray((tampered / "storage.tar.enc").read_bytes())
    data[len(data) // 2] ^= 0x01
    (tampered / "storage.tar.enc").write_bytes(bytes(data))
    with pytest.raises(Backup.BackupError, match="failed authentication"):
        Backup.restore_backup(tampered, key, spare, tmp_path / "t1")

    truncated = tmp_path / "truncated"
    shutil.copytree(backup.path, truncated)
    part = (truncated / "database.dump.enc").read_bytes()
    (truncated / "database.dump.enc").write_bytes(part[: len(part) // 2])
    with pytest.raises(Backup.BackupError):
        Backup.restore_backup(truncated, key, spare, tmp_path / "t2")


def test_backups_need_a_valid_key(fresh, tmp_path):
    for bad, message in ((None, "not set"), ("not base64!", "not valid base64"), ("AAAA", "32 bytes")):
        with pytest.raises(Backup.BackupError, match=message):
            Backup.create_backup(fresh[0], fresh[1], tmp_path, bad)


def test_chunked_encryption_round_trips_large_files(tmp_path):
    key = Backup.load_key(Backup.new_key())
    src = tmp_path / "big.bin"
    src.write_bytes(os.urandom(Backup.CHUNK * 2 + 123))  # three chunks, the last partial
    Backup.encrypt_file(src, tmp_path / "big.enc", key)
    Backup.decrypt_file(tmp_path / "big.enc", tmp_path / "big.out", key)
    assert (tmp_path / "big.out").read_bytes() == src.read_bytes()
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    Backup.encrypt_file(empty, tmp_path / "empty.enc", key)
    Backup.decrypt_file(tmp_path / "empty.enc", tmp_path / "empty.out", key)
    assert (tmp_path / "empty.out").read_bytes() == b""
