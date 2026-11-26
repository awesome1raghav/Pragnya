"""Error envelope, request IDs and database-down behaviour. No PostgreSQL needed."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import NextronError


def test_database_down_liveness_still_answers(database_down_app):
    with TestClient(database_down_app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ALIVE"


def test_database_down_readiness_is_503(database_down_app):
    with TestClient(database_down_app) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_NOT_READY"
    check = body["error"]["details"]["checks"]["database"]
    assert check == {
        "status": "FAIL",
        "reachable": False,
        "migrations_current": False,
        "latency_ms": None,
        "reason": "Database is unreachable",
    }


def test_database_down_system_status_is_503_without_leaking_connection_details(database_down_app):
    with TestClient(database_down_app) as client:
        response = client.get("/api/v1/system/database")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    # psycopg raises OperationalError or a subclass of it; on Windows a closed port
    # usually times out (ConnectionTimeout) rather than being refused.
    assert body["error"]["details"]["error_type"] in {"OperationalError", "ConnectionTimeout"}
    assert body["error"]["details"]["last_successful_check"] is None
    assert "unused" not in response.text  # the password in the URL
    assert "127.0.0.1" not in response.text


def test_validation_error_envelope(database_down_app):
    @database_down_app.get("/test-only/validate")
    def validate(count: int) -> dict:
        return {"count": count}

    with TestClient(database_down_app) as client:
        response = client.get("/test-only/validate", params={"count": "many"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["location"] == ["query", "count"]
    assert response.headers["X-Request-ID"] == body["meta"]["request_id"]


def test_unexpected_error_is_500_without_internals(database_down_app):
    @database_down_app.get("/test-only/crash")
    def crash() -> dict:
        raise RuntimeError("internal secret detail")

    with TestClient(database_down_app, raise_server_exceptions=False) as client:
        response = client.get("/test-only/crash")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred", "details": None}
    assert "internal secret detail" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["X-Request-ID"] == body["meta"]["request_id"]


def test_nextron_error_keeps_its_code(database_down_app):
    @database_down_app.get("/test-only/missing")
    def missing() -> dict:
        raise NextronError(404, "EVIDENCE_NOT_FOUND", "The requested evidence does not exist")

    with TestClient(database_down_app) as client:
        response = client.get("/test-only/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"


def test_settings_reject_non_psycopg_driver():
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://user:pw@localhost/db", _env_file=None)


def test_cors_origins_parse_from_comma_list():
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://user:pw@localhost/db",
        CORS_ORIGINS="http://localhost:8080, http://127.0.0.1:8080",
        _env_file=None,
    )
    assert settings.CORS_ORIGINS == ["http://localhost:8080", "http://127.0.0.1:8080"]
