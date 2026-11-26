"""NEXTRON API entry point.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -m uvicorn Backend.App.Main:app --host 127.0.0.1 --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Backend.App.Api.V1.Router import api_router
from Backend.App.Config import Settings, get_settings
from Backend.App.Core.Exceptions import register_exception_handlers
from Backend.App.Core.Middleware import RequestIdMiddleware
from Backend.App.Core.RequestContext import REQUEST_ID_HEADER
from Backend.App.Lifespan import lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="NEXTRON digital media forensic investigation API. Responses use the {success, data, meta} envelope.",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Order matters: the last middleware added runs first. Request IDs wrap everything,
    # so CORS responses and errors carry X-Request-ID too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
