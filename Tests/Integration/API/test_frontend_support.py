"""Endpoints added for the Step 1 frontend: case objectives/category/last activity, global evidence list, search."""

import uuid

import pytest

pytestmark = pytest.mark.postgres

API = "/api/v1"


def make_case(client, **fields):
    response = client.post(f"{API}/cases", json={"title": "Frontend support case", **fields})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def upload_png(client, case_id, media, name="photo.png"):
    response = client.post(f"{API}/cases/{case_id}/evidence", files={"file": (name, media["png"], "image/png")})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_case_objectives_category_and_last_activity(client):
    case = make_case(client, objectives="Establish whether the clip was edited", category="MEDIA_MANIPULATION")
    assert case["objectives"] == "Establish whether the clip was edited"
    assert case["category"] == "MEDIA_MANIPULATION"
    created_activity = case["last_activity_at"]
    assert created_activity is not None

    patched = client.patch(f"{API}/cases/{case['case_id']}", json={"category": "SOURCE_VERIFICATION", "objectives": None}).json()["data"]
    assert patched["category"] == "SOURCE_VERIFICATION" and patched["objectives"] is None
    assert patched["last_activity_at"] > created_activity

    assert make_case(client)["category"] == "OTHER"  # default
    assert client.post(f"{API}/cases", json={"title": "x", "category": "CRIME"}).status_code == 422
    assert client.patch(f"{API}/cases/{case['case_id']}", json={"category": None}).status_code == 422


def test_cases_sort_by_last_activity(client):
    first, second = make_case(client, title="sort-a"), make_case(client, title="sort-b")
    client.patch(f"{API}/cases/{first['case_id']}", json={"notes": "touched later"})
    listed = client.get(f"{API}/cases", params={"sort_by": "last_activity_at", "sort_order": "desc", "page_size": 5}).json()["data"]
    ids = [c["case_id"] for c in listed]
    assert ids.index(first["case_id"]) < ids.index(second["case_id"])


def test_global_evidence_list_filters_and_names_the_case(client, media):
    case = make_case(client, title="Global list case")
    evidence = upload_png(client, case["case_id"], media, "unique-global-name.png")

    scoped = client.get(f"{API}/evidence", params={"case_id": case["case_id"]}).json()
    assert scoped["pagination"]["total_items"] == 1
    row = scoped["data"][0]
    assert row["evidence_id"] == evidence["evidence_id"]
    assert row["case_number"] == case["case_number"] and row["case_title"] == "Global list case"

    by_name = client.get(f"{API}/evidence", params={"search": "unique-global"}).json()["data"]
    assert [r["evidence_id"] for r in by_name] == [evidence["evidence_id"]]
    by_hash = client.get(f"{API}/evidence", params={"search": evidence["sha256"][:10]}).json()["data"]
    assert evidence["evidence_id"] in [r["evidence_id"] for r in by_hash]
    by_number = client.get(f"{API}/evidence", params={"search": evidence["evidence_number"]}).json()["data"]
    assert evidence["evidence_id"] in [r["evidence_id"] for r in by_number]

    assert client.get(f"{API}/evidence", params={"media_type": "FILM"}).status_code == 422
    missing = client.get(f"{API}/evidence", params={"case_id": str(uuid.uuid4())})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_search_finds_cases_and_evidence_and_names_unsearched_types(client, media):
    marker = uuid.uuid4().hex[:8]
    case = make_case(client, title=f"Search {marker} case")
    evidence = upload_png(client, case["case_id"], media, f"{marker}-frame.png")

    body = client.get(f"{API}/search", params={"q": marker}).json()["data"]
    types = {(h["type"], h["id"]) for h in body["hits"]}
    assert ("CASE", case["case_id"]) in types and ("EVIDENCE", evidence["evidence_id"]) in types
    assert body["searched_types"] == ["CASE", "EVIDENCE"]
    assert body["not_searchable_yet"] == ["SOURCE", "FINDING", "REPORT"]

    archived = make_case(client, title=f"Archived {marker}")
    client.post(f"{API}/cases/{archived['case_id']}/archive")
    assert archived["case_id"] in [h["id"] for h in client.get(f"{API}/search", params={"q": f"Archived {marker}"}).json()["data"]["hits"]]

    assert client.get(f"{API}/search", params={"q": "x"}).status_code == 422
