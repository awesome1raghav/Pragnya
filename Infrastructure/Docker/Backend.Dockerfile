# syntax=docker/dockerfile:1
# NEXTRON backend image: the API and the worker (same code, different command), plus the test suite.
# Build from the repository root:  docker build -f Infrastructure/Docker/Backend.Dockerfile -t nextron-backend .
#
# Lean by design: the runtime dependencies from Backend/pyproject.toml, pinned to Backend/requirements.txt. PyTorch
# (detectors, visual search) is not installed: those features report themselves unavailable, as they do anywhere the
# weights are missing. FFmpeg comes from Debian; pg_dump/pg_restore 17 from the PostgreSQL apt repository (backups).

FROM python:3.11.9-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 \
 && apt-get purge -y gnupg && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/nextron

# dependencies first, so code changes do not reinstall them
COPY Backend/pyproject.toml Backend/requirements.txt /tmp/deps/
RUN python -c "import tomllib; p = tomllib.load(open('/tmp/deps/pyproject.toml', 'rb'))['project']; print('\n'.join(p['dependencies'] + p['optional-dependencies']['test']))" > /tmp/deps/runtime.txt \
 && grep -v '^--' /tmp/deps/requirements.txt | sed 's/+cpu//' > /tmp/deps/constraints.txt \
 && pip install -r /tmp/deps/runtime.txt -c /tmp/deps/constraints.txt

COPY VERSION ./
COPY Backend/ Backend/
COPY Database/ Database/
COPY Scripts/ Scripts/
COPY ["Documentation/Architecture/Module Connectivity.md", "Documentation/Architecture/"]
COPY Tests/conftest.py Tests/conftest.py
COPY Tests/Unit/ Tests/Unit/
COPY Tests/Integration/ Tests/Integration/
RUN useradd --create-home --uid 10001 nextron && install -d -o nextron /data/storage
USER nextron
ENV STORAGE_ROOT=/data/storage PG_TOOLS=local FFPROBE_PATH=ffprobe DETECTORS_ENABLED=false
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).status == 200 else 1)"
# migrations run first; the API refuses ENVIRONMENT=production without authentication (Backend/App/Main.py)
CMD ["sh", "-c", "python -m alembic -c Database/PostgreSQL/alembic.ini upgrade head && exec uvicorn Backend.App.Main:app --host 0.0.0.0 --port 8000"]
