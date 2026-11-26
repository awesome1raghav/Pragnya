"""NEX-CM: case CRUD, lifecycle, statistics and events against real PostgreSQL."""

import re
import uuid

import pytest

pytestmark = pytest.mark.postgres

API = "/api/v1"


def create(client, **fields):
    body = {"title": "Suspicious video investigation", **fields}
    response = client.post(f"{API}/cases", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def events_of(client, case_id):
    return [e["event_type"] for e in client.get(f"{API}/cases/{case_id}/events?limit=200").json()["data"]]


def test_create_case_persists_with_event(client):
    response = client.post(
        f"{API}/cases",
        json={"title": "  Suspicious video  ", "description": "Initial report", "priority": "HIGH", "tags": ["video", "video", "audio"]},
    )
    assert response.status_code == 201
    body = response.json()
    case = body["data"]
    assert body["success"] is True and body["message"] == "Investigation created successfully"
    assert re.fullmatch(r"CASE-\d{4,}", case["case_number"])
    assert case["title"] == "Suspicious video"
    assert case["status"] == "OPEN"
    assert case["priority"] == "HIGH"
    assert case["tags"] == ["video", "audio"]
    assert case["created_by"] == "local-operator"
    assert case["revision"] == 1 and case["evidence_count"] == 0

    fetched = client.get(f"{API}/cases/{case['case_id']}").json()["data"]
    assert fetched == case
    assert events_of(client, case["case_id"]) == ["case.created"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "ok", "priority": "URGENT"},
        {"title": "ok", "status": "CLOSED"},  # status is not client-settable
        {"description": "no title"},
        {"title": "ok", "tags": [""]},
    ],
)
def test_create_case_rejects_invalid_input(client, body):
    response = client.post(f"{API}/cases", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_and_malformed_case_ids(client):
    missing = client.get(f"{API}/cases/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CASE_NOT_FOUND"
    assert client.get(f"{API}/cases/not-a-uuid").status_code == 422


def test_patch_updates_fields_records_changes_and_ignores_no_ops(client):
    case = create(client, priority="LOW")
    case_id = case["case_id"]

    patched = client.patch(f"{API}/cases/{case_id}", json={"priority": "CRITICAL", "notes": "Escalated"})
    assert patched.status_code == 200
    data = patched.json()["data"]
    assert data["priority"] == "CRITICAL" and data["notes"] == "Escalated" and data["revision"] == 2

    same = client.patch(f"{API}/cases/{case_id}", json={"priority": "CRITICAL"}).json()["data"]
    assert same["revision"] == 2  # nothing changed, no new revision or event

    events = client.get(f"{API}/cases/{case_id}/events").json()["data"]
    assert [e["event_type"] for e in events] == ["case.created", "case.updated"]
    assert events[1]["payload"]["changes"] == {
        "priority": {"from": "LOW", "to": "CRITICAL"},
        "notes": {"from": None, "to": "Escalated"},
    }


@pytest.mark.parametrize("body", [{"status": "CLOSED"}, {"title": None}, {"title": ""}, {"case_number": 7}])
def test_patch_rejects_disallowed_fields(client, body):
    case = create(client)
    response = client.patch(f"{API}/cases/{case['case_id']}", json=body)
    assert response.status_code == 422


def test_archive_and_reopen_follow_lifecycle_rules(client):
    case = create(client)
    case_id = case["case_id"]

    archived = client.post(f"{API}/cases/{case_id}/archive", json={"reason": "Duplicate report"})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "ARCHIVED"
    assert archived.json()["data"]["archived_at"] is not None

    again = client.post(f"{API}/cases/{case_id}/archive")
    assert again.status_code == 409 and again.json()["error"]["code"] == "CASE_ARCHIVED"
    blocked = client.patch(f"{API}/cases/{case_id}", json={"title": "Changed"})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "CASE_ARCHIVED"

    reopened = client.post(f"{API}/cases/{case_id}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "OPEN"  # restores the status it was archived from
    assert reopened.json()["data"]["archived_at"] is None

    not_archived = client.post(f"{API}/cases/{case_id}/reopen")
    assert not_archived.status_code == 409 and not_archived.json()["error"]["code"] == "CASE_NOT_ARCHIVED"

    events = client.get(f"{API}/cases/{case_id}/events").json()["data"]
    assert [e["event_type"] for e in events] == ["case.created", "case.archived", "case.reopened"]
    assert events[1]["payload"]["reason"] == "Duplicate report"


def test_list_filters_search_sort_and_paginate(client):
    marker = uuid.uuid4().hex[:8]
    made = [create(client, title=f"{marker} case {i}", priority=p) for i, p in enumerate(["LOW", "HIGH", "HIGH"])]
    client.post(f"{API}/cases/{made[0]['case_id']}/archive")

    listed = client.get(f"{API}/cases", params={"search": marker, "page_size": 1, "sort_by": "title", "sort_order": "asc"})
    assert listed.status_code == 200
    body = listed.json()
    assert body["pagination"] == {"page": 1, "page_size": 1, "total_items": 2, "total_pages": 2, "has_next": True, "has_previous": False}
    assert body["data"][0]["title"] == f"{marker} case 1"  # archived case 0 excluded by default

    archived = client.get(f"{API}/cases", params={"search": marker, "status": "ARCHIVED"}).json()
    assert [c["case_id"] for c in archived["data"]] == [made[0]["case_id"]]

    high = client.get(f"{API}/cases", params={"search": marker, "priority": "HIGH"}).json()
    assert high["pagination"]["total_items"] == 2

    by_number = client.get(f"{API}/cases", params={"search": made[2]["case_number"]}).json()
    assert made[2]["case_id"] in [c["case_id"] for c in by_number["data"]]

    bad = client.get(f"{API}/cases", params={"status": "ACTIVE"})
    assert bad.status_code == 422 and bad.json()["error"]["details"] == {"invalid": ["ACTIVE"]}
    assert client.get(f"{API}/cases", params={"page_size": 101}).status_code == 422


def test_statistics_count_real_rows(client):
    before = client.get(f"{API}/cases/statistics").json()["data"]
    create(client, priority="CRITICAL")
    after = client.get(f"{API}/cases/statistics").json()["data"]
    assert after["total_cases"] == before["total_cases"] + 1
    assert after["by_priority"]["CRITICAL"] == before["by_priority"]["CRITICAL"] + 1
    assert set(after["by_status"]) == {
        "OPEN", "EVIDENCE_COLLECTION", "INVESTIGATION_IN_PROGRESS", "REVIEW_REQUIRED",
        "REVIEW_COMPLETED", "REPORT_AVAILABLE", "CLOSED", "ARCHIVED",
    }


def test_event_cursor_pages_without_gaps(client):
    case = create(client)
    case_id = case["case_id"]
    for i in range(4):
        client.patch(f"{API}/cases/{case_id}", json={"notes": f"note {i}"})

    first = client.get(f"{API}/cases/{case_id}/events", params={"limit": 2}).json()
    assert len(first["data"]) == 2 and first["cursor"]["has_more"] is True
    second = client.get(f"{API}/cases/{case_id}/events", params={"limit": 10, "after": first["cursor"]["next_after"]}).json()
    assert second["cursor"]["has_more"] is False and second["cursor"]["next_after"] is None
    sequences = [e["sequence"] for e in first["data"] + second["data"]]
    assert len(sequences) == 5 and sequences == sorted(sequences)


def test_summary_and_case_statistics(client):
    case = create(client)
    summary = client.get(f"{API}/cases/{case['case_id']}/summary").json()["data"]
    assert summary["case"]["case_id"] == case["case_id"]
    assert summary["statistics"]["evidence_total"] == 0
    assert summary["statistics"]["evidence_by_media_type"] == {"IMAGE": 0, "VIDEO": 0, "AUDIO": 0}
    assert summary["recent_events"][0]["event_type"] == "case.created"
