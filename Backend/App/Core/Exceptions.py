"""Structured API errors and the handlers that render every failure as an ErrorEnvelope.

No handler returns a stack trace; unexpected errors are logged server-side with the request ID.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from Backend.App.Core.RequestContext import get_request_id
from Backend.App.Schemas.Common import ErrorBody, ErrorEnvelope

logger = logging.getLogger("nextron.api")


class ErrorCode:
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    # Cases (NEX-CM)
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    CASE_ARCHIVED = "CASE_ARCHIVED"
    CASE_NOT_ARCHIVED = "CASE_NOT_ARCHIVED"
    # Acquisition and evidence (NEX-CAP / NEX-EVD / NEX-MET)
    INVALID_UPLOAD = "INVALID_UPLOAD"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    INVALID_MEDIA_FORMAT = "INVALID_MEDIA_FORMAT"
    MEDIA_PROBE_UNAVAILABLE = "MEDIA_PROBE_UNAVAILABLE"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    EVIDENCE_FILE_MISSING = "EVIDENCE_FILE_MISSING"
    METADATA_NOT_FOUND = "METADATA_NOT_FOUND"
    PRESERVATION_FAILED = "PRESERVATION_FAILED"
    # Jobs, T-MIR runs and analysis
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_NOT_CANCELLABLE = "JOB_NOT_CANCELLABLE"
    JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RESULT_NOT_FOUND = "RESULT_NOT_FOUND"
    NOTIFICATION_NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    NO_EVIDENCE = "NO_EVIDENCE"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_FILE_MISSING = "ARTIFACT_FILE_MISSING"
    UNKNOWN_MODULE = "UNKNOWN_MODULE"


_STATUS_CODES = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
}


class NextronError(Exception):
    """Raise from services or routes to return a specific structured error."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(status_code: int, code: str, message: str, details: Any = None, headers=None) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


async def _nextron_error(_: Request, exc: NextronError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.BAD_REQUEST)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    if exc.status_code == 404 and message == "Not Found":
        message = "The requested resource does not exist"
    return error_response(exc.status_code, code, message, None, headers=getattr(exc, "headers", None))


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(error.get("loc", ())), "message": error.get("msg", ""), "type": error.get("type", "")}
        for error in exc.errors()
    ]
    return error_response(422, ErrorCode.VALIDATION_ERROR, "The request failed validation", details)


async def _database_error(_: Request, exc: DBAPIError) -> JSONResponse:
    logger.warning("Database error on request %s: %s", get_request_id(), exc.__class__.__name__)
    return error_response(503, ErrorCode.DATABASE_UNAVAILABLE, "The database is unavailable", None)


def register_exception_handlers(app: FastAPI) -> None:
    """Unexpected exceptions are rendered by RequestIdMiddleware, inside the request-ID scope."""
    app.add_exception_handler(NextronError, _nextron_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(OperationalError, _database_error)
    app.add_exception_handler(DBAPIError, _database_error)
