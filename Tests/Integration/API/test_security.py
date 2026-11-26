"""Step 9 security: cross-site writes are refused (WebSockets: see test_tmir), responses carry protective headers, mutations are
rate limited, and production without authentication is refused."""

import pytest
from fastapi.testclient import TestClient

from Backend.App.Config import get_settings
from Backend.App.Main import create_app
from Tests.Integration.Orchestration.test_tmir import API, api, fresh, new_case  # noqa: F401 — fixtures
from Tests.conftest import build_app

pytestmark = pytest.mark.postgres
EVIL = {"Origin": "https://attacker.example"}
OURS = {"Origin": "http://localhost:8080"}


def test_cross_site_writes_are_refused_but_same_site_and_tools_pass(api, media):
    case_id = new_case(api)
    files = {"file": ("x.png", media["png"], "image/png")}
    refused = api.post(f"{API}/cases/{case_id}/evidence", files=files, headers=EVIL)  # what a hostile page's form would send
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"
    assert api.post(f"{API}/cases", json={"title": "from a hostile page"}, headers=EVIL).status_code == 403
    assert api.get(f"{API}/cases/{case_id}/evidence").json()["pagination"]["total_items"] == 0  # nothing was stored

    assert api.post(f"{API}/cases/{case_id}/evidence", files=files, headers=OURS).status_code == 201  # the NEXTRON frontend
    assert api.post(f"{API}/cases", json={"title": "scripted"}).status_code == 201  # no Origin: curl, scripts
    assert api.get(f"{API}/cases", headers=EVIL).status_code == 200  # reads are left to CORS (the browser hides the body)


def test_protective_headers(api):
    r = api.get(f"{API}/cases")
    for name, value in {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer",
                        "cross-origin-resource-policy": "same-site", "cache-control": "no-store"}.items():
        assert r.headers[name] == value, name


def test_mutations_are_rate_limited(fresh):
    with TestClient(build_app(fresh[0], fresh[1], RATE_LIMIT_MUTATIONS_PER_MINUTE=3)) as client:
        codes = [client.post(f"{API}/cases", json={"title": f"t{i}"}).status_code for i in range(4)]
        assert codes == [201, 201, 201, 429]
        limited = client.post(f"{API}/cases", json={"title": "again"})
        assert limited.json()["error"]["code"] == "RATE_LIMITED" and int(limited.headers["retry-after"]) >= 1
        assert client.get(f"{API}/cases").status_code == 200  # reads are not limited


def test_production_without_authentication_is_refused():
    with pytest.raises(RuntimeError, match="no authentication"):
        create_app(get_settings().model_copy(update={"ENVIRONMENT": "production"}))
