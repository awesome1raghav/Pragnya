"""Shared fixtures.

PostgreSQL fixtures connect to the server named by TEST_DATABASE_URL, or else by the
backend's DATABASE_URL, and create uniquely named throwaway databases on it. If the server
is unreachable those tests fail; they are never skipped or faked.
"""

import io
import math
import os
import shutil
import struct
import subprocess
import uuid
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PIL import Image
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.engine import URL, make_url

from Backend.App.Config import get_settings
from Backend.App.Main import create_app
from Backend.App.Services.HealthService import ALEMBIC_INI
from Backend.App.Utils.MediaProbe import resolve_executable
from Backend.App.Workers.Worker import Worker
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine

# Nothing listens on port 1; used to simulate PostgreSQL being down.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nextron:unused@127.0.0.1:1/nextron"


def _server_url() -> URL:
    return make_url(os.environ.get("TEST_DATABASE_URL") or get_settings().DATABASE_URL)


def _render(url: URL) -> str:
    return url.render_as_string(hide_password=False)


def alembic_config(database_url: str) -> AlembicConfig:
    config = AlembicConfig(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def build_app(database_url: str, storage_root: Path | None = None, **overrides) -> FastAPI:
    """An app on the given database. Tests always pass their own storage root, never Backend/Storage."""
    # Detectors are off unless a test turns them on: measurement tests must not depend on 2.6 GB of weights.
    # The Neo4j projection is off too; Tests/Integration/Projection turns it on against a disposable graph.
    update = {"DATABASE_URL": database_url, "ENVIRONMENT": "testing", "DETECTORS_ENABLED": False,
              "NEO4J_URI": "", "QDRANT_URL": "", "WEB_VISUAL_SEARCH_ENABLED": False,
              "SERPAPI_API_KEY": "", **overrides}
    if storage_root is not None:
        update["STORAGE_ROOT"] = Path(storage_root)
    return create_app(get_settings().model_copy(update=update))


def make_worker(app: FastAPI, **kwargs) -> Worker:
    """A worker on the app's database and storage, run in-process by tests (the real one is a separate process)."""
    worker = Worker(app.state.settings, app.state.session_factory, app.state.storage,
                    worker_id=kwargs.pop("worker_id", f"test-worker-{uuid.uuid4().hex[:6]}"), **kwargs)
    worker.register()
    return worker


def run_worker(app: FastAPI, *, max_jobs: int = 50, **kwargs) -> list[uuid.UUID]:
    """Processes queued jobs until none is runnable; returns the IDs of the jobs it ran."""
    worker = make_worker(app, **kwargs)
    ran = []
    for _ in range(max_jobs):
        job_id = worker.process_one()
        if job_id is None:
            break
        ran.append(job_id)
    return ran


@pytest.fixture(scope="session")
def storage_root(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("evidence-storage")


@pytest.fixture(scope="session")
def admin_engine() -> Iterator[Engine]:
    engine = create_database_engine(
        _render(_server_url().set(database="postgres")),
        EngineOptions(pooled=False, application_name="nextron-tests"),
    ).execution_options(isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:  # fails here, loudly, if the server is down
        connection.execute(text("SELECT 1"))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def database_factory(admin_engine: Engine) -> Iterator[Callable[[], tuple[str, str]]]:
    """Returns a function that creates an empty database and gives back (name, url)."""
    created: list[str] = []

    def create() -> tuple[str, str]:
        name = f"nextron_test_{uuid.uuid4().hex[:10]}"
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
        return name, _render(_server_url().set(database=name))

    yield create

    with admin_engine.connect() as connection:
        for name in created:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture(scope="session")
def migrated_database(database_factory) -> tuple[str, str]:
    name, url = database_factory()
    command.upgrade(alembic_config(url), "head")
    return name, url


@pytest.fixture()
def client(migrated_database, storage_root) -> Iterator[TestClient]:
    with TestClient(build_app(migrated_database[1], storage_root)) as test_client:
        yield test_client


@pytest.fixture()
def unmigrated_client(database_factory, tmp_path) -> Iterator[TestClient]:
    _, url = database_factory()
    with TestClient(build_app(url, tmp_path)) as test_client:
        yield test_client


@pytest.fixture()
def database_down_app(tmp_path) -> FastAPI:
    return build_app(UNREACHABLE_DATABASE_URL, tmp_path, DATABASE_CONNECT_TIMEOUT_SECONDS=1)


# --- media fixtures, generated fresh for every run (no binary files in Git) -------------------


def _ffmpeg_executable() -> str:
    ffprobe = resolve_executable(get_settings().FFPROBE_PATH)
    candidates = []
    if ffprobe:
        candidates.append(Path(ffprobe).with_name(Path(ffprobe).name.replace("ffprobe", "ffmpeg")))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("FFmpeg is required to generate the video test fixture")


@pytest.fixture(scope="session")
def media(tmp_path_factory) -> dict[str, bytes]:
    folder = tmp_path_factory.mktemp("media-fixtures")
    out: dict[str, bytes] = {}

    gradient = Image.linear_gradient("L").resize((64, 48)).convert("RGB")
    buffer = io.BytesIO()
    gradient.save(buffer, "PNG")
    out["png"] = buffer.getvalue()

    exif = Image.Exif()
    exif[0x010F] = "NEXTRON Test Camera"  # Make
    exif[0x0110] = "Fixture Model"  # Model
    exif.get_ifd(0x8769)[0x9003] = "2026:01:02 03:04:05"  # DateTimeOriginal
    buffer = io.BytesIO()
    gradient.save(buffer, "JPEG", exif=exif, quality=90)
    out["jpeg_exif"] = buffer.getvalue()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 8000))) for i in range(4000)))
    out["wav"] = buffer.getvalue()

    mp4 = folder / "clip.mp4"
    subprocess.run(
        [_ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
         "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(mp4)],
        check=True, capture_output=True, timeout=60,
    )
    out["mp4"] = mp4.read_bytes()

    out["text_as_jpg"] = b"This is plain text pretending to be a JPEG.\n" * 4
    out["truncated_png"] = out["png"][:40]
    out["heic"] = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
    return out
