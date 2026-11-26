# Third-Party Components and Licences

Direct backend dependencies as pinned in `Backend/pyproject.toml`. Licences are as published by
each project on PyPI; re-check when upgrading. The full transitive set is in `Backend/requirements.txt`.

| Component | Version | Licence | Purpose |
|---|---|---|---|
| FastAPI | 0.165.0 | MIT | HTTP API framework, OpenAPI |
| Uvicorn (standard extras) | 0.54.0 | BSD-3-Clause | ASGI server |
| Pydantic | 2.14.4 | MIT | Validation and schemas |
| pydantic-settings | 2.16.3 | MIT | Environment configuration |
| SQLAlchemy | 2.1.9 | MIT | Database toolkit and ORM |
| Alembic | 1.20.1 | MIT | Schema migrations |
| psycopg (binary) | 3.3.9 | LGPL-3.0 | PostgreSQL driver |
| python-multipart | 0.0.34 | Apache-2.0 | Streaming multipart parser for evidence uploads |
| Pillow | 13.0.0 | MIT-CMU | Image validation, decoding and EXIF |
| pytest | 9.2.0 | MIT | Tests (development only) |
| HTTPX | 0.28.1 | BSD-3-Clause | Test client transport (development only) |

Infrastructure: PostgreSQL 17.12 (`postgres:17.12-alpine` image), PostgreSQL Licence.

External tool, not bundled: FFprobe/FFmpeg (installed separately; tested with the 9.1 "full" Windows
build from gyan.dev, which is GPL-licensed). NEXTRON runs it as a separate process only.
