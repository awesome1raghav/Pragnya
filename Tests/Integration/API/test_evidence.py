"""NEX-CAP / NEX-EVD / NEX-MET against real PostgreSQL, real files and real FFprobe/Pillow."""

import hashlib
import os
import stat
import uuid
from datetime import timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from Backend.App.Modules.NexEvd.StorageReconciliation import reconcile
from Backend.App.Storage.LocalStorage import LocalStorage
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Session import create_session_factory
from Tests.conftest import alembic_config, build_app, run_worker

pytestmark = pytest.mark.postgres

API = "/api/v1"


def new_case(client):
    response = client.post(f"{API}/cases", json={"title": "Evidence test case"})
    assert response.status_code == 201
    return response.json()["data"]["case_id"]


def upload(client, case_id, data: bytes, filename="file.bin", content_type="application/octet-stream", **fields):
    return client.post(f"{API}/cases/{case_id}/evidence", files={"file": (filename, data, content_type)}, data=fields)


def stored_path(storage_root, evidence):
    return storage_root / "Originals" / evidence["case_id"] / evidence["evidence_id"]


def staging_files(storage_root):
    return list((storage_root / "Temporary").glob("*.part"))


def test_png_upload_is_hashed_preserved_and_described(client, media, storage_root):
    case_id = new_case(client)
    response = upload(client, case_id, media["png"], "photo.png", "image/png", description="Submitted photo")
    assert response.status_code == 201, response.text
    evidence = response.json()["data"]

    assert evidence["sha256"] == hashlib.sha256(media["png"]).hexdigest()
    assert evidence["file_size"] == len(media["png"])
    assert (evidence["media_type"], evidence["detected_format"], evidence["mime_type"]) == ("IMAGE", "png", "image/png")
    assert evidence["preservation_status"] == "PRESERVED"
    assert evidence["filename"] == "photo.png" and evidence["description"] == "Submitted photo"
    assert evidence["analysis_job"]["state"] == "QUEUED"  # metadata is extracted by T-MIR in a worker, not in the request
    assert evidence["duplicates_in_case"] == []
    assert "storage_key" not in evidence

    path = stored_path(storage_root, evidence)
    assert path.read_bytes() == media["png"]
    assert not os.access(path, os.W_OK)  # originals are read-only
    assert staging_files(storage_root) == []

    metadata_before = client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata")
    assert metadata_before.status_code == 404 and metadata_before.json()["error"]["code"] == "METADATA_NOT_FOUND"
    assert evidence["analysis_job"]["job_id"] in {str(j) for j in run_worker(client.app)}

    metadata = client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]
    assert metadata["extractor"] == "pillow"
    assert metadata["input_sha256"] == evidence["sha256"]
    assert (metadata["summary"]["width"], metadata["summary"]["height"]) == (64, 48)
    assert metadata["summary"]["exif_present"] is False

    case = client.get(f"{API}/cases/{case_id}").json()["data"]
    assert case["status"] == "EVIDENCE_COLLECTION" and case["evidence_count"] == 1

    history = [e["event_type"] for e in client.get(f"{API}/evidence/{evidence['evidence_id']}/history").json()["data"]]
    assert history == ["evidence.received", "evidence.hashed", "evidence.preserved", "evidence.metadata_extracted"]


def test_jpeg_exif_is_extracted_and_timestamps_labelled(client, media):
    evidence = upload(client, new_case(client), media["jpeg_exif"], "camera.jpg", "image/jpeg").json()["data"]
    run_worker(client.app)
    summary = client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]["summary"]
    assert summary["exif"]["Make"] == "NEXTRON Test Camera"
    assert summary["exif"]["Model"] == "Fixture Model"
    assert summary["embedded_timestamps"] == {"DateTimeOriginal": "2026:01:02 03:04:05"}
    assert "may be absent, wrong or edited" in summary["embedded_timestamps_note"]


def test_wav_is_audio_with_ffprobe_metadata(client, media):
    evidence = upload(client, new_case(client), media["wav"], "voice.wav", "audio/wav").json()["data"]
    assert (evidence["media_type"], evidence["mime_type"]) == ("AUDIO", "audio/wav")
    run_worker(client.app)
    metadata = client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]
    assert metadata["extractor"] == "ffprobe" and metadata["extractor_version"].startswith("ffprobe version")
    audio = metadata["summary"]["audio_streams"][0]
    assert (audio["sample_rate_hz"], audio["channels"]) == (8000, 1)
    assert metadata["summary"]["container"]["duration_seconds"] == pytest.approx(0.5, abs=0.01)
    assert metadata["raw"]["format"]["format_name"] == "wav"


def test_mp4_is_video_with_streams(client, media):
    evidence = upload(client, new_case(client), media["mp4"], "clip.mp4", "video/mp4").json()["data"]
    assert (evidence["media_type"], evidence["detected_format"], evidence["mime_type"]) == ("VIDEO", "mp4", "video/mp4")
    run_worker(client.app)
    summary = client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]["summary"]
    video = summary["video_streams"][0]
    assert (video["codec"], video["width"], video["height"], video["average_frame_rate"]) == ("h264", 160, 120, 25.0)
    assert summary["has_audio"] is True and summary["audio_streams"][0]["codec"] == "aac"


@pytest.mark.parametrize(
    ("fixture", "filename", "content_type"),
    [("text_as_jpg", "fake.jpg", "image/jpeg"), ("truncated_png", "broken.png", "image/png"), ("heic", "phone.heic", "image/heic")],
)
def test_invalid_media_is_rejected_and_nothing_is_kept(client, media, storage_root, fixture, filename, content_type):
    case_id = new_case(client)
    response = upload(client, case_id, media[fixture], filename, content_type)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "INVALID_MEDIA_FORMAT"
    assert client.get(f"{API}/cases/{case_id}/evidence").json()["pagination"]["total_items"] == 0
    assert staging_files(storage_root) == []


def test_upload_size_limit_is_enforced_while_streaming(migrated_database, tmp_path, media):
    with TestClient(build_app(migrated_database[1], tmp_path, MAX_UPLOAD_SIZE_BYTES=4096)) as small:
        case_id = new_case(small)
        response = upload(small, case_id, media["mp4"], "clip.mp4", "video/mp4")
        assert response.status_code == 413
        assert response.json()["error"] == {
            "code": "UPLOAD_TOO_LARGE", "message": "The uploaded file exceeds the size limit", "details": {"max_bytes": 4096}
        }
        assert staging_files(tmp_path) == []


def test_malformed_upload_requests(client, media):
    case_id = new_case(client)
    url = f"{API}/cases/{case_id}/evidence"

    not_multipart = client.post(url, content=media["png"], headers={"Content-Type": "image/png"})
    assert not_multipart.status_code == 415 and not_multipart.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    no_file = client.post(url, data={"description": "nothing attached"}, files={"other": ("x", b"y")})
    assert no_file.status_code == 400 and no_file.json()["error"]["code"] == "INVALID_UPLOAD"

    two_files = client.post(url, files=[("file", ("a.png", media["png"], "image/png")), ("file", ("b.png", media["png"], "image/png"))])
    assert two_files.status_code == 400

    empty = upload(client, case_id, b"", "empty.png", "image/png")
    assert empty.status_code == 400 and empty.json()["error"]["message"] == "The uploaded file is empty"

    bad_enum = upload(client, case_id, media["png"], "a.png", "image/png", source_type="SCRAPED")
    assert bad_enum.status_code == 422 and "source_type" in bad_enum.json()["error"]["details"]

    assert upload(client, str(uuid.uuid4()), media["png"]).status_code == 404


def test_upload_to_archived_case_is_refused(client, media):
    case_id = new_case(client)
    client.post(f"{API}/cases/{case_id}/archive")
    response = upload(client, case_id, media["png"], "a.png", "image/png")
    assert response.status_code == 409 and response.json()["error"]["code"] == "CASE_ARCHIVED"


def test_filename_is_a_label_only(client, media, storage_root):
    # (httpx percent-encodes control characters in filenames, so those are covered by the unit test)
    evidence = upload(client, new_case(client), media["png"], "..\\..\\Windows\\evil<name>.png", "image/png").json()["data"]
    assert evidence["filename"] == "evil<name>.png"
    assert stored_path(storage_root, evidence).is_file()


def test_duplicate_bytes_get_separate_records_and_are_flagged(client, media):
    case_id = new_case(client)
    first = upload(client, case_id, media["png"], "a.png", "image/png").json()["data"]
    second = upload(client, case_id, media["png"], "copy.png", "image/png").json()["data"]
    assert second["evidence_id"] != first["evidence_id"]
    assert second["sha256"] == first["sha256"]
    assert second["duplicates_in_case"] == [{"evidence_id": first["evidence_id"], "evidence_number": first["evidence_number"]}]


def test_integrity_match_then_tamper_then_missing(client, media, storage_root):
    evidence = upload(client, new_case(client), media["png"], "a.png", "image/png").json()["data"]
    evidence_id = evidence["evidence_id"]
    assert client.get(f"{API}/evidence/{evidence_id}/integrity").json()["data"]["last_verification"] is None

    match = client.post(f"{API}/evidence/{evidence_id}/verify-integrity").json()
    assert match["data"]["result"] == "MATCH" and match["message"] == "Stored bytes match the recorded SHA-256"

    path = stored_path(storage_root, evidence)
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    with open(path, "ab") as handle:
        handle.write(b"tampered")
    mismatch = client.post(f"{API}/evidence/{evidence_id}/verify-integrity").json()["data"]
    assert mismatch["result"] == "MISMATCH"
    assert mismatch["recorded_sha256"] == evidence["sha256"]
    assert mismatch["computed_sha256"] == hashlib.sha256(media["png"] + b"tampered").hexdigest()
    assert client.get(f"{API}/evidence/{evidence_id}").json()["data"]["sha256"] == evidence["sha256"]  # never overwritten
    state = client.get(f"{API}/evidence/{evidence_id}/integrity").json()["data"]
    assert state["last_verification"]["result"] == "MISMATCH"

    path.unlink()
    missing = client.post(f"{API}/evidence/{evidence_id}/verify-integrity").json()["data"]
    assert missing["result"] == "MISSING" and missing["computed_sha256"] is None
    gone = client.get(f"{API}/evidence/{evidence_id}/preview")
    assert gone.status_code == 410 and gone.json()["error"]["code"] == "EVIDENCE_FILE_MISSING"

    history = [e["event_type"] for e in client.get(f"{API}/evidence/{evidence_id}/history").json()["data"]]
    assert history[-3:] == ["evidence.integrity_verified", "evidence.integrity_mismatch", "evidence.integrity_missing"]


def test_preview_serves_inert_inline_bytes_with_ranges(client, media):
    evidence = upload(client, new_case(client), media["mp4"], "clip.mp4", "video/mp4").json()["data"]
    url = f"{API}/evidence/{evidence['evidence_id']}/preview"

    full = client.get(url)
    assert full.status_code == 200 and full.content == media["mp4"]
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["content-disposition"].startswith("inline")
    assert full.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in full.headers["content-security-policy"]
    assert full.headers["x-evidence-sha256"] == evidence["sha256"]

    part = client.get(url, headers={"Range": "bytes=0-9"})
    assert part.status_code == 206 and part.content == media["mp4"][:10]


def test_download_is_an_attachment_and_a_custody_event(client, media):
    evidence = upload(client, new_case(client), media["wav"], "voice.wav", "audio/wav").json()["data"]
    response = client.get(f"{API}/evidence/{evidence['evidence_id']}/download")
    assert response.status_code == 200 and response.content == media["wav"]
    assert response.headers["content-disposition"].startswith("attachment")
    assert 'filename="voice.wav"' in response.headers["content-disposition"]
    assert response.headers["x-evidence-sha256"] == evidence["sha256"]
    history = [e["event_type"] for e in client.get(f"{API}/evidence/{evidence['evidence_id']}/history").json()["data"]]
    assert history[-1] == "evidence.downloaded"


def test_records_and_bytes_survive_an_api_restart(migrated_database, storage_root, media):
    url = migrated_database[1]
    with TestClient(build_app(url, storage_root)) as first_process:
        case_id = new_case(first_process)
        evidence = upload(first_process, case_id, media["jpeg_exif"], "camera.jpg", "image/jpeg").json()["data"]
        run_worker(first_process.app)

    with TestClient(build_app(url, storage_root)) as second_process:  # new engine, pool and app state
        assert second_process.get(f"{API}/cases/{case_id}").json()["data"]["evidence_count"] == 1
        assert second_process.get(f"{API}/evidence/{evidence['evidence_id']}").json()["data"] == {
            k: v for k, v in evidence.items() if k not in ("duplicates_in_case", "analysis_job")
        }
        assert second_process.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]["status"] == "EXTRACTED"
        assert second_process.post(f"{API}/evidence/{evidence['evidence_id']}/verify-integrity").json()["data"]["result"] == "MATCH"


def test_database_refuses_to_rewrite_custody(client, migrated_database, media):
    evidence = upload(client, new_case(client), media["png"], "a.png", "image/png").json()["data"]
    run_worker(client.app)
    engine = create_database_engine(migrated_database[1], EngineOptions(pooled=False))
    try:
        for statement in (
            "UPDATE evidence SET sha256 = repeat('0', 64) WHERE id = :id",
            "UPDATE evidence SET storage_key = 'Originals/x/y' WHERE id = :id",
            "DELETE FROM evidence WHERE id = :id",
            "UPDATE investigation_events SET actor = 'someone else' WHERE evidence_id = :id",
            "DELETE FROM investigation_events WHERE evidence_id = :id",
            "UPDATE evidence_metadata SET status = 'FAILED' WHERE evidence_id = :id",
        ):
            with engine.begin() as connection, pytest.raises(DBAPIError, match="not permitted|cannot be changed"):
                connection.execute(text(statement), {"id": evidence["evidence_id"]})
        with engine.begin() as connection:  # annotations remain editable
            connection.execute(text("UPDATE evidence SET description = 'annotated' WHERE id = :id"), {"id": evidence["evidence_id"]})
    finally:
        engine.dispose()


def test_reconciliation_reports_orphans_missing_and_stale_staging(database_factory, tmp_path, media):
    _, url = database_factory()
    command.upgrade(alembic_config(url), "head")
    with TestClient(build_app(url, tmp_path)) as isolated:
        kept = upload(isolated, new_case(isolated), media["png"], "a.png", "image/png").json()["data"]
        lost = upload(isolated, new_case(isolated), media["wav"], "b.wav", "audio/wav").json()["data"]

    orphan = tmp_path / "Originals" / str(uuid.uuid4()) / str(uuid.uuid4())
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"bytes without a record")
    lost_path = stored_path(tmp_path, lost)
    os.chmod(lost_path, stat.S_IREAD | stat.S_IWRITE)
    lost_path.unlink()
    stale = tmp_path / "Temporary" / "interrupted.part"
    stale.write_bytes(b"half an upload")
    os.utime(stale, (0, 0))
    fresh = tmp_path / "Temporary" / "in-progress.part"
    fresh.write_bytes(b"still arriving")

    engine = create_database_engine(url, EngineOptions(pooled=False))
    try:
        with create_session_factory(engine)() as session:
            storage = LocalStorage(tmp_path)
            report = reconcile(session, storage, stale_after=timedelta(hours=1))
            assert report.referenced_originals == 2
            assert report.orphan_originals == [f"Originals/{orphan.parent.name}/{orphan.name}"]
            assert report.missing_originals == [lost["evidence_id"]]
            assert report.stale_staging == ["interrupted.part"]
            assert stale.exists() and not report.clean

            cleaned = reconcile(session, storage, stale_after=timedelta(hours=1), delete_stale_staging=True)
            assert cleaned.deleted_staging == ["interrupted.part"]
            assert not stale.exists() and fresh.exists() and orphan.exists()  # originals never touched
            assert stored_path(tmp_path, kept).exists()
    finally:
        engine.dispose()


def test_evidence_statistics_and_storage_status(client, media):
    before = client.get(f"{API}/evidence/statistics").json()["data"]
    upload(client, new_case(client), media["wav"], "c.wav", "audio/wav")
    after = client.get(f"{API}/evidence/statistics").json()["data"]
    assert after["by_media_type"]["AUDIO"] == before["by_media_type"]["AUDIO"] + 1
    assert after["total_bytes"] == before["total_bytes"] + len(media["wav"])

    storage = client.get(f"{API}/system/storage")
    assert storage.status_code == 200 and storage.json()["data"]["writable"] is True
    ready = client.get(f"{API}/health/ready").json()["data"]["checks"]
    assert ready["storage"] == {"status": "PASS", "writable": True, "reason": None}
