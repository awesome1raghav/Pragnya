"""Encrypted backup and verified restore of PostgreSQL and evidence storage (Step 9).

A backup is a directory with three files:
  database.dump.enc   pg_dump (custom format) of the NEXTRON database
  storage.tar.enc     Originals/, Derived/ and Reports/ under STORAGE_ROOT (Temporary/ is not backed up)
  manifest.json       when, from which migration head, row counts per table, every evidence item's SHA-256 and storage
                      key, and the SHA-256 of both plaintext parts. Not secret; it lets a restore prove completeness.

Both parts are encrypted with AES-256-GCM in 8 MiB chunks. Each chunk has its own nonce and is authenticated with its
index and a "last chunk" flag, so reordering, truncation or any changed byte makes the restore stop. The key
(BACKUP_ENCRYPTION_KEY, 32 random bytes as base64) is never written into the backup: keep a copy somewhere else, or
the backup cannot be read.

Restore goes into a NEW, empty database and a NEW storage root, never over the live ones. It then checks: migration head
and row counts equal the manifest's, and every evidence file's SHA-256 equals the recorded one.

PostgreSQL client tools: PG_TOOLS=docker:<container> (default docker:nextron-postgres) runs pg_dump / pg_restore inside
the Compose container; PG_TOOLS=local uses them from PATH.
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

MAGIC = b"NXBK1"
CHUNK = 8 * 1024 * 1024
PARTS = ("Originals", "Derived", "Reports")
FORMAT = "nextron-backup/1"


class BackupError(Exception):
    pass


# ── encryption ──────────────────────────────────────────────────────────────────────────────
def load_key(value: str | None) -> bytes:
    if not value:
        raise BackupError("BACKUP_ENCRYPTION_KEY is not set: backups are always encrypted")
    try:
        key = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise BackupError("BACKUP_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != 32:
        raise BackupError("BACKUP_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def new_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def _aad(index: int, last: bool) -> bytes:
    return index.to_bytes(8, "big") + (b"\x01" if last else b"\x00")


def encrypt_file(src: Path, dst: Path, key: bytes) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aead, prefix = AESGCM(key), os.urandom(4)
    size = src.stat().st_size
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(MAGIC + prefix)
        index, done = 0, 0
        while True:
            chunk = fin.read(CHUNK)
            done += len(chunk)
            last = done >= size
            sealed = aead.encrypt(prefix + index.to_bytes(8, "big"), chunk, _aad(index, last))
            fout.write(len(sealed).to_bytes(4, "big") + sealed)
            index += 1
            if last:
                return


def decrypt_file(src: Path, dst: Path, key: bytes) -> None:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aead = AESGCM(key)
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        head = fin.read(len(MAGIC) + 4)
        if head[:len(MAGIC)] != MAGIC:
            raise BackupError(f"{src.name} is not a NEXTRON backup part")
        prefix, index = head[len(MAGIC):], 0
        while True:
            raw = fin.read(4)
            if len(raw) < 4:
                raise BackupError(f"{src.name} is truncated: its last chunk is missing")
            sealed = fin.read(int.from_bytes(raw, "big"))
            nonce = prefix + index.to_bytes(8, "big")
            for last in (False, True):
                try:
                    plain = aead.decrypt(nonce, sealed, _aad(index, last))
                    break
                except InvalidTag:
                    plain = None
            if plain is None:
                raise BackupError(f"{src.name} failed authentication at chunk {index}: wrong key, or the file was changed")
            fout.write(plain)
            index += 1
            if last:
                if fin.read(1):
                    raise BackupError(f"{src.name} has data after its last chunk")
                return


# ── PostgreSQL client tools ─────────────────────────────────────────────────────────────────
def _pg(tool: str, url: str, args: list[str], *, stdin=None, stdout=None) -> None:
    u = make_url(url)
    mode = os.environ.get("PG_TOOLS", "docker:nextron-postgres")
    if mode == "local":
        cmd = [tool, "-h", u.host or "127.0.0.1", "-p", str(u.port or 5432), "-U", u.username, *args]
        env = os.environ | {"PGPASSWORD": u.password or ""}
    elif mode.startswith("docker:"):
        docker = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        cmd = [docker, "exec", "-i", mode.split(":", 1)[1], tool, "-U", u.username, *args]  # local socket inside the container
        env = None
    else:
        raise BackupError(f"PG_TOOLS must be 'local' or 'docker:<container>', not {mode!r}")
    result = subprocess.run(cmd, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, env=env, check=False)
    if result.returncode != 0:
        raise BackupError(f"{tool} failed: {result.stderr.decode(errors='replace').strip()[:500]}")


def snapshot(url: str) -> dict:
    engine = create_engine(url)
    try:
        with engine.connect() as c:
            tables = sorted(t for t in inspect(c).get_table_names() if t != "alembic_version")
            counts = {t: c.execute(text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in tables}
            head = [r[0] for r in c.execute(text("SELECT version_num FROM alembic_version"))]
            evidence = [{"evidence_id": str(r[0]), "sha256": r[1], "storage_key": r[2]}
                        for r in c.execute(text("SELECT id, sha256, storage_key FROM evidence ORDER BY evidence_number"))]
    finally:
        engine.dispose()
    return {"alembic_head": head, "row_counts": counts, "evidence": evidence}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ── backup ──────────────────────────────────────────────────────────────────────────────────
@dataclass
class BackupResult:
    path: Path
    manifest: dict


def create_backup(database_url: str, storage_root: Path, out_root: Path, key_b64: str | None) -> BackupResult:
    key = load_key(key_b64)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_root / f"NEXTRON-{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="nextron-backup-") as tmp:
        dump, archive = Path(tmp) / "database.dump", Path(tmp) / "storage.tar"
        state = snapshot(database_url)  # before the dump: a row added in between is in the dump, never missing from it
        with open(dump, "wb") as f:
            _pg("pg_dump", database_url, ["-d", make_url(database_url).database, "-Fc", "--no-owner"], stdout=f)
        with tarfile.open(archive, "w") as tar:
            for part in PARTS:
                if (storage_root / part).exists():
                    tar.add(storage_root / part, arcname=part)
        manifest = {"format": FORMAT, "created_at": datetime.now(timezone.utc).isoformat(), **state,
                    "parts": {"database.dump": {"sha256": _sha(dump), "bytes": dump.stat().st_size},
                              "storage.tar": {"sha256": _sha(archive), "bytes": archive.stat().st_size}},
                    "encryption": "AES-256-GCM, 8 MiB chunks, key not stored"}
        encrypt_file(dump, target / "database.dump.enc", key)
        encrypt_file(archive, target / "storage.tar.enc", key)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return BackupResult(target, manifest)


# ── restore ─────────────────────────────────────────────────────────────────────────────────
def restore_backup(backup: Path, key_b64: str | None, target_url: str, target_storage: Path) -> dict:
    key = load_key(key_b64)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise BackupError("Unknown backup format")
    if target_storage.exists() and any(target_storage.iterdir()):
        raise BackupError(f"{target_storage} is not empty; restore only into a new storage root")
    engine = create_engine(target_url)
    try:
        with engine.connect() as c:
            if inspect(c).get_table_names():
                raise BackupError("The target database is not empty; restore only into a new database")
    finally:
        engine.dispose()
    with tempfile.TemporaryDirectory(prefix="nextron-restore-") as tmp:
        dump, archive = Path(tmp) / "database.dump", Path(tmp) / "storage.tar"
        decrypt_file(backup / "database.dump.enc", dump, key)
        decrypt_file(backup / "storage.tar.enc", archive, key)
        for name, path in (("database.dump", dump), ("storage.tar", archive)):
            if _sha(path) != manifest["parts"][name]["sha256"]:
                raise BackupError(f"{name} does not match the manifest's SHA-256")
        with open(dump, "rb") as f:
            _pg("pg_restore", target_url, ["-d", make_url(target_url).database, "--no-owner", "--exit-on-error"], stdin=f)
        target_storage.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(target_storage, filter="data")  # refuses absolute paths, "..", links outside the root
    return verify(manifest, target_url, target_storage)


def verify(manifest: dict, url: str, storage_root: Path) -> dict:
    state = snapshot(url)
    problems = []
    if state["alembic_head"] != manifest["alembic_head"]:
        problems.append(f"migration head {state['alembic_head']} != {manifest['alembic_head']}")
    for table, n in manifest["row_counts"].items():
        if state["row_counts"].get(table) != n:
            problems.append(f"{table}: {state['row_counts'].get(table)} rows, manifest {n}")
    checked = 0
    for e in manifest["evidence"]:
        path = storage_root / e["storage_key"]
        if not path.is_file():
            problems.append(f"{e['evidence_id']}: original missing")
        elif _sha(path) != e["sha256"]:
            problems.append(f"{e['evidence_id']}: SHA-256 differs")
        else:
            checked += 1
    report = {"ok": not problems, "tables": len(manifest["row_counts"]), "rows": sum(manifest["row_counts"].values()),
              "evidence_verified": checked, "evidence_total": len(manifest["evidence"]), "problems": problems}
    if problems:
        raise BackupError("Restore verification failed: " + "; ".join(problems[:10]))
    return report
