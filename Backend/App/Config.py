"""Application settings, read from environment variables and Backend/.env.

There are deliberately no default credentials: DATABASE_URL must be supplied,
so a missing configuration fails loudly instead of connecting somewhere unexpected.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


def _read_version() -> str:
    version_file = PROJECT_ROOT / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    APP_NAME: str = "NEXTRON API"
    APP_VERSION: str = Field(default_factory=_read_version)
    API_V1_PREFIX: str = "/api/v1"

    # SQLAlchemy URL, e.g. postgresql+psycopg://user:password@127.0.0.1:5433/nextron
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DATABASE_MAX_OVERFLOW: int = Field(default=5, ge=0, le=50)
    DATABASE_POOL_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = Field(default=3, ge=1, le=60)

    # Comma-separated list of browser origins allowed to call the API.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:8080", "http://127.0.0.1:8080"]

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Recorded as the actor on events. There is no authentication yet: the API is a
    # single-operator local service bound to 127.0.0.1 (archive §3.1, §17.1).
    OPERATOR_NAME: str = Field(default="local-operator", min_length=1, max_length=100)

    # Protected local evidence storage (ignored by Git). Originals are written once, read-only.
    STORAGE_ROOT: Path = BACKEND_ROOT / "Storage"
    MAX_UPLOAD_SIZE_BYTES: int = Field(default=500 * 1024 * 1024, ge=1024)

    # FFprobe/FFmpeg executables: a name looked up on PATH, or an absolute path.
    FFPROBE_PATH: str = "ffprobe"
    FPCALC_PATH: str = "fpcalc"  # Chromaprint, optional: NEX-AUD reports its absence
    MEDIA_PROBE_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=600)

    # T-MIR, jobs and workers (plan Step 3)
    AUTO_ANALYZE_ON_UPLOAD: bool = True          # each preserved upload queues an investigation run for it
    JOB_LEASE_SECONDS: int = Field(default=30, ge=5, le=3600)
    JOB_HEARTBEAT_SECONDS: float = Field(default=5.0, gt=0, le=600)
    JOB_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    JOB_RETRY_BASE_SECONDS: float = Field(default=5.0, ge=0, le=3600)
    JOB_TIMEOUT_SECONDS: int = Field(default=1800, ge=10, le=86_400)
    MODULE_TIMEOUT_SECONDS: float = Field(default=600.0, gt=0, le=86_400)
    WORKER_POLL_SECONDS: float = Field(default=1.0, gt=0, le=60)
    OUTBOX_POLL_SECONDS: float = Field(default=0.5, gt=0, le=60)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg:// driver")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
