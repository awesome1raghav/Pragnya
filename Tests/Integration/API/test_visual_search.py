"""Visual search never claims external coverage and rejects unsafe/invalid queries."""

import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient

from Tests.conftest import build_app

pytestmark = pytest.mark.postgres


def test_local_visual_search_states_and_validation(client, media):
    created = client.post("/api/v1/cases", json={"title": "Visual query validation"})
    assert created.status_code == 201
    case_id = created.json()["data"]["case_id"]
    status = client.get("/api/v1/visual-search/status")
    assert status.status_code == 200
    assert status.json()["data"]["local"]["configured"] is False
    assert status.json()["data"]["web"]["configured"] is False

    path = f"/api/v1/cases/{case_id}/visual-search"
    assert client.post(path, data={"mode": "web"}, files={"file": ("q.png", media["png"], "image/png")}).json()["error"]["code"] == "WEB_SEARCH_DISABLED"
    assert client.post(path, data={"url": "http://127.0.0.1/private"}).json()["error"]["code"] == "INVALID_SEARCH_URL"
    assert client.post(path, data={"top_k": 51}, files={"file": ("q.png", media["png"], "image/png")}).status_code == 422
    assert client.post(path, data={"crop": "not-json"}, files={"file": ("q.png", media["png"], "image/png")}).status_code == 422
    assert client.post(path, files={"file": ("q.png", media["png"], "image/png")}).json()["error"]["code"] == "VISUAL_SEARCH_UNAVAILABLE"


def test_web_search_needs_explicit_consent_and_uses_provider_results(migrated_database, storage_root, media, monkeypatch):
    from Backend.App.Api.V1 import VisualSearch

    called = []

    def provider(image, key, top_k):
        called.append((image.size, key, top_k))
        return [{"page_url": "https://example.org/story", "image_url": "https://example.org/photo.jpg",
                 "title": "Example", "match_type": "VISUAL_MATCH", "score": None, "score_kind": None}]

    monkeypatch.setattr(VisualSearch, "web_search", provider)
    with TestClient(build_app(migrated_database[1], storage_root, WEB_VISUAL_SEARCH_ENABLED=True,
                              SERPAPI_API_KEY=SecretStr("test-key"))) as client:
        case = client.post("/api/v1/cases", json={"title": "Web query validation"}).json()["data"]["case_id"]
        path = f"/api/v1/cases/{case}/visual-search"
        state = client.get("/api/v1/visual-search/status").json()["data"]
        assert state["web"] == {"configured": True, "provider": "serpapi_google_lens"}
        no_consent = client.post(path, data={"mode": "web"}, files={"file": ("q.png", media["png"], "image/png")})
        assert no_consent.status_code == 403
        assert not called
        response = client.post(path, data={"mode": "web", "allow_external": "true", "top_k": "3"},
                               files={"file": ("q.png", media["png"], "image/png")})
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["scope"] == "web" and result["provider"] == "serpapi_google_lens"
        assert result["matches"][0]["score"] is None
        token = result["matches"][0]["thumbnail_token"]
        assert len(token) >= 24
        assert len(result["query_sha256"]) == 64
        assert called[0][1:] == ("test-key", 3)
        monkeypatch.setattr(VisualSearch, "render", lambda value: media["jpeg_exif"] if value == token else b"")
        preview = client.get(f"/api/v1/visual-search/thumbnails/{token}")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/jpeg"
        assert preview.headers["cache-control"] == "private, max-age=600"
