"""Step 8: preferences (applied by the backend, optimistic concurrency), notification choices, read events that other
tabs follow, search across every stored resource, and non-secret configuration."""

import pytest
from sqlalchemy import select

from Backend.App.Realtime.Notifications import NotificationConsumer
from Database.PostgreSQL.Models import OutboxEvent
from Tests.Integration.Orchestration.test_sources_lineage import drain
from Tests.Integration.Orchestration.test_tmir import API, api, db, fresh, new_case, upload  # noqa: F401 — fixtures

pytestmark = pytest.mark.postgres


def _events(client, event_type):
    with db(client) as session:
        return session.scalars(select(OutboxEvent).where(OutboxEvent.event_type == event_type).order_by(OutboxEvent.sequence)).all()


def test_preferences_are_versioned_and_stale_saves_are_refused(api):
    start = api.get(f"{API}/preferences").json()["data"]
    assert start["version"] == 0 and start["updated_at"] is None
    assert start["preferences"]["notifications"]["runs_completed"] is True and start["preferences"]["analysis"]["auto_analyze_on_upload"] is None
    assert start["effective"]["auto_analyze_on_upload"] is True  # the server default

    first = api.patch(f"{API}/preferences", json={"version": 0, "preferences": {"notifications": {"runs_completed": False}}}).json()["data"]
    assert first["version"] == 1 and first["preferences"]["notifications"]["runs_completed"] is False
    assert first["preferences"]["notifications"]["runs_failed"] is True  # untouched fields keep their values

    stale = api.patch(f"{API}/preferences", json={"version": 0, "preferences": {"reports": {"default_download": "json"}}})  # a second tab
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "PREFERENCES_CONFLICT"
    assert stale.json()["error"]["details"]["current_version"] == 1
    assert api.get(f"{API}/preferences").json()["data"]["preferences"]["reports"]["default_download"] == "pdf"  # nothing applied

    bad = api.patch(f"{API}/preferences", json={"version": 1, "preferences": {"notifications": {"everything": True}}})
    assert bad.status_code == 422
    assert api.patch(f"{API}/preferences", json={"version": 1, "preferences": {"reports": {"default_download": "xml"}}}).status_code == 422
    assert [e.payload["version"] for e in _events(api, "preferences.updated")] == [1]  # other tabs refresh on this event


def test_preferences_are_applied_by_the_backend(api, media):
    api.patch(f"{API}/preferences", json={"version": 0, "preferences": {"analysis": {"auto_analyze_on_upload": False},
                                                                        "notifications": {"runs_completed": False, "runs_partial": False}}})
    case_id = new_case(api)
    off = upload(api, case_id, media["png"], "a.png", "image/png")
    assert off["analysis_job"] is None  # no run queued

    api.patch(f"{API}/preferences", json={"version": 1, "preferences": {"analysis": {"auto_analyze_on_upload": True}}})
    on = upload(api, case_id, media["jpeg_exif"], "b.jpg", "image/jpeg")
    assert on["analysis_job"] is not None
    drain(api)
    with db(api) as session:
        NotificationConsumer(gap_timeout=0, operator=api.app.state.settings.OPERATOR_NAME).process(session)
    kinds = {n["event_type"] for n in api.get(f"{API}/notifications").json()["data"]}
    assert not kinds & {"job.completed", "job.partially_completed"}  # turned off


def test_reading_notifications_is_an_event_other_tabs_follow(api, media):
    upload(api, new_case(api), media["png"], "a.png", "image/png")
    drain(api)
    with db(api) as session:
        NotificationConsumer(gap_timeout=0, operator=api.app.state.settings.OPERATOR_NAME).process(session)
    items = api.get(f"{API}/notifications").json()["data"]
    assert items
    api.patch(f"{API}/notifications/{items[0]['notification_id']}/read")
    api.patch(f"{API}/notifications/{items[0]['notification_id']}/read")  # already read: no second event
    api.post(f"{API}/notifications/read-all")
    assert [e.payload["count"] for e in _events(api, "notification.read")] == [1] + ([len(items) - 1] if len(items) > 1 else [])


def test_search_covers_sources_findings_reports_and_reviews(api, media):
    case_id = new_case(api)
    evidence = upload(api, case_id, media["jpeg_exif"], "harbour.jpg", "image/jpeg")
    api.post(f"{API}/cases/{case_id}/sources", json={"url": "https://www.youtube.com/watch?v=harbourfire"})  # needs a connector; no request made
    drain(api)
    api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "CASE_CONCLUSION", "subject_id": case_id, "decision": "INCONCLUSIVE",
                                                     "rationale": "Waiting for the harbour authority footage"})
    report = api.post(f"{API}/cases/{case_id}/reports", json={"kind": "DRAFT"}).json()["data"]

    def types(q):
        body = api.get(f"{API}/search", params={"q": q}).json()["data"]
        assert body["not_searchable_yet"] == [] and set(body["searched_types"]) == {"CASE", "EVIDENCE", "SOURCE", "FINDING", "REPORT", "REVIEW"}
        return {h["type"]: h for h in body["hits"]}

    hits = types("harbour")
    assert {"EVIDENCE", "SOURCE", "REVIEW"} <= set(hits)
    assert hits["SOURCE"]["case_id"] == case_id and hits["REVIEW"]["subtitle"].startswith("REV-")
    assert types(report["report_number"])["REPORT"]["id"] == report["report_id"]
    finding = types("metadata")["FINDING"]  # NEX-MET's finding title
    assert finding["evidence_id"] == evidence["evidence_id"]
    assert types("100%_") == {}  # LIKE wildcards are matched literally, not as match-all


def test_system_config_has_no_secrets(api):
    cfg = api.get(f"{API}/system/config").json()["data"]
    assert cfg["environment"] == "testing" and cfg["detectors"]["enabled"] is False and cfg["projections"]["neo4j"] is False
    text = str(cfg).lower()
    settings = api.app.state.settings
    assert "postgresql" not in text and "password" not in text and str(settings.STORAGE_ROOT).lower() not in text


def test_recent_findings_across_investigations(api, media):
    a, b = new_case(api), new_case(api)
    upload(api, a, media["png"], "a.png", "image/png")
    upload(api, b, media["jpeg_exif"], "b.jpg", "image/jpeg")
    drain(api)
    rows = api.get(f"{API}/findings", params={"limit": 50}).json()["data"]
    assert {r["case_id"] for r in rows} == {a, b} and all(r["evidence"][0]["evidence_number"].startswith("EVD-") for r in rows if r["evidence"])
    obs = api.get(f"{API}/findings", params={"assertion": "OBSERVATION", "limit": 50}).json()["data"]
    assert obs and {r["assertion"] for r in obs} == {"OBSERVATION"}
    assert [r["created_at"] for r in rows] == sorted((r["created_at"] for r in rows), reverse=True)
    assert api.get(f"{API}/findings", params={"assertion": "GUESS"}).status_code == 422
