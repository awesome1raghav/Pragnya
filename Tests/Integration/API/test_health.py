"""Health, readiness and /system/database against a real PostgreSQL."""

from datetime import datetime

import pytest

from Backend.App.Config import PROJECT_ROOT

pytestmark = pytest.mark.postgres


def _assert_meta(response):
    body = response.json()
    meta = body["meta"]
    assert meta["request_id"].startswith("req_")
    assert response.headers["X-Request-ID"] == meta["request_id"]
    assert meta["timestamp"].endswith("Z")
    datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00"))
    return body


def test_liveness_reports_running_api(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = _assert_meta(response)
    assert body["success"] is True
    assert body["data"]["status"] == "ALIVE"
    assert body["data"]["version"] == (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert body["data"]["environment"] == "testing"


def test_readiness_passes_on_migrated_database(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = _assert_meta(response)
    check = body["data"]["checks"]["database"]
    assert body["data"]["status"] == "READY"
    assert check["status"] == "PASS"
    assert check["reachable"] is True
    assert check["migrations_current"] is True
    assert check["latency_ms"] > 0


def test_system_database_reports_measured_values(client, migrated_database):
    response = client.get("/api/v1/system/database")
    assert response.status_code == 200
    data = _assert_meta(response)["data"]
    assert data["status"] == "HEALTHY"
    assert data["database"] == "postgresql"
    assert data["server_version"].startswith("17.")
    assert data["database_name"] == migrated_database[0]
    assert data["migrations"] == {"current": ["0005"], "head": ["0005"], "up_to_date": True}
    assert data["latency_ms"] > 0
    assert data["connection_pool"]["maximum"] == 10  # pool_size 5 + max_overflow 5
    assert data["last_successful_check"] == data["checked_at"]


def test_each_probe_is_a_new_measurement(client):
    first = client.get("/api/v1/system/database").json()["data"]["checked_at"]
    second = client.get("/api/v1/system/database").json()["data"]["checked_at"]
    assert second > first


def test_unmigrated_database_is_reachable_but_not_ready(unmigrated_client):
    ready = unmigrated_client.get("/api/v1/health/ready")
    assert ready.status_code == 503
    body = _assert_meta(ready)
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_NOT_READY"
    check = body["error"]["details"]["checks"]["database"]
    assert check["reachable"] is True
    assert check["migrations_current"] is False
    assert check["reason"] == "Database schema is not at the migration head"

    status = unmigrated_client.get("/api/v1/system/database")
    assert status.status_code == 200
    assert status.json()["data"]["status"] == "DEGRADED"
    assert status.json()["data"]["migrations"]["current"] == []


def test_client_request_id_is_echoed(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "frontend-abc.123"})
    assert response.headers["X-Request-ID"] == "frontend-abc.123"
    assert response.json()["meta"]["request_id"] == "frontend-abc.123"


def test_malformed_request_id_is_replaced(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad id <script>"})
    assert response.headers["X-Request-ID"].startswith("req_")


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = _assert_meta(response)
    assert body == {
        "success": False,
        "error": {"code": "NOT_FOUND", "message": "The requested resource does not exist", "details": None},
        "meta": body["meta"],
    }


def test_wrong_method_uses_error_envelope(client):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_cors_allows_web_frontend_only(client):
    allowed = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8080"

    refused = client.options(
        "/api/v1/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in refused.headers


def test_openapi_and_docs_list_the_routes(client):
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    for path in ("/api/v1/health", "/api/v1/health/ready", "/api/v1/system/database"):
        assert path in paths
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger-ui" in docs.text.lower()
