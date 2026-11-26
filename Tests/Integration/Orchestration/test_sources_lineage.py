"""Step 5 through the real worker: NEX-SRC retrieves sources from a local web server (its address exempted only for
these tests), retrieved media becomes evidence with custody and its own run, NEX-FPM fingerprints and matches, NEX-MOC
proposes candidate relationships ordered by the sources' claimed publication times."""

import http.server
import io
import subprocess
import threading
import uuid

import pytest
from PIL import Image
from sqlalchemy import func, select, text

from Database.PostgreSQL.Models import MediaFingerprint, MediaRelationship, SourceObservation
from Tests.Integration.Orchestration.test_tmir import API, api, db, fresh, new_case, upload  # noqa: F401 — fixtures
from Tests.conftest import make_worker

pytestmark = pytest.mark.postgres


def drain(client, rounds: int = 40) -> None:
    worker = make_worker(client.app)
    worker.allow_addresses = frozenset({"127.0.0.1"})
    for _ in range(rounds):
        if worker.process_one() is None:
            return


class _Site(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802
        status, ctype, body = self.routes.get(self.path, (404, "text/plain", b"missing"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def site():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Site.routes
    httpd.shutdown()
    _Site.routes = {}


def _photo() -> Image.Image:
    import numpy as np

    rng = np.random.default_rng(11)
    y, x = np.mgrid[0:360, 0:480]
    base = np.stack([120 + 80 * np.sin(x / 37.0), 110 + 70 * np.cos(y / 23.0), 90 + 60 * np.sin((x + y) / 51.0)], axis=-1)
    base[120:240, 160:330] = [200, 60, 40]
    return Image.fromarray((base + rng.normal(0, 6, base.shape)).clip(0, 255).astype("uint8"))


def _bytes(im: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def _page(media: str, published: str, title: str) -> bytes:
    return (f'<html><head><title>{title}</title><meta property="og:title" content="{title}">'
            f'<meta property="og:image" content="{media}"><meta property="article:published_time" content="{published}">'
            "</head><body><script>alert(1)</script></body></html>").encode()


def test_sources_are_retrieved_preserved_fingerprinted_and_ordered(api, site, media):
    base, routes = site
    original = _photo()
    routes["/later.html"] = (200, "text/html; charset=utf-8", _page("/img/small.jpg", "2024-03-01T10:00:00Z", "Repost"))
    routes["/img/small.jpg"] = (200, "image/jpeg", _bytes(original.resize((240, 180)), "JPEG", quality=70))
    routes["/earlier.html"] = (200, "text/html", _page(base + "/img/full.png", "2023-11-05T08:30:00+00:00", "First post"))
    routes["/img/full.png"] = (200, "image/png", _bytes(original, "PNG"))
    routes["/gone"] = (404, "text/plain", b"no")

    case_id = new_case(api)
    uploaded = upload(api, case_id, _bytes(original, "PNG"), "from-witness.png", "image/png")
    unrelated = upload(api, case_id, media["png"], "unrelated.png", "image/png")
    later = api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/later.html?utm_source=feed"})
    assert later.status_code == 202 and later.json()["data"]["state"] == "PENDING"
    assert later.json()["data"]["normalized_url"] == base + "/later.html"
    earlier = api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/earlier.html"}).json()["data"]
    gone = api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/gone"}).json()["data"]
    assert api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/later.html"}).json()["error"]["code"] == "SOURCE_EXISTS"
    assert api.post(f"{API}/cases/{case_id}/sources", json={"url": "file:///etc/passwd"}).json()["error"]["code"] == "INVALID_SOURCE_URL"

    drain(api)  # source jobs, then the investigation runs they queued, then the uploads' runs

    later_rec = api.get(f"{API}/sources/{later.json()['data']['source_id']}").json()["data"]
    earlier_rec = api.get(f"{API}/sources/{earlier['source_id']}").json()["data"]
    assert (later_rec["state"], later_rec["title"], later_rec["claimed_publication_time"]) == ("RETRIEVED", "Repost", "2024-03-01T10:00:00Z")
    assert earlier_rec["state"] == "RETRIEVED" and earlier_rec["evidence_id"]
    assert api.get(f"{API}/sources/{gone['source_id']}").json()["data"]["state"] == "NOT_FOUND"

    history = api.get(f"{API}/sources/{later_rec['source_id']}/history").json()["data"]
    assert [h["outcome"] for h in history] == ["RETRIEVED"] and [r["status"] for r in history[0]["redirects"]] == [200, 200]
    assert history[0]["metadata"]["media_url"].endswith("/img/small.jpg")
    retrieved = api.get(f"{API}/evidence/{later_rec['evidence_id']}").json()["data"]
    assert (retrieved["source_type"], retrieved["acquisition_method"]) == ("SOURCE_RETRIEVAL", "CONNECTOR_RETRIEVAL")
    custody = [e["event_type"] for e in api.get(f"{API}/evidence/{later_rec['evidence_id']}/history").json()["data"]]
    assert custody[:3] == ["evidence.received", "evidence.hashed", "evidence.preserved"]

    # NEX-FPM: each item fingerprinted once; the repost matches the witness copy
    with db(api) as session:
        assert session.scalar(select(func.count()).select_from(MediaFingerprint)) == 4 * 2  # 4 images x (pHash, dHash)
    fpm = api.get(f"{API}/cases/{case_id}/modules/NEX-FPM/results").json()["data"]["evidence"]
    by_id = {e["evidence_id"]: e for e in fpm}
    candidates = [f for e in fpm for f in e["findings"] if f["finding_type"] == "SIMILAR_MEDIA_CANDIDATE"]
    assert candidates and all(f["score_kind"] == "DISTANCE" for f in candidates)
    assert not any(unrelated["evidence_id"] in f["evidence_ids"] for f in candidates)
    assert by_id[unrelated["evidence_id"]]["status"] == "COMPLETED"

    # NEX-MOC: three candidate relationships among the three copies; the one with the earlier claimed time is "earlier observed"
    with db(api) as session:
        rels = session.scalars(select(MediaRelationship).where(MediaRelationship.superseded_at.is_(None))).all()
        pairs = {frozenset({str(r.evidence_a), str(r.evidence_b)}): r for r in rels}
    copies = {uploaded["evidence_id"], later_rec["evidence_id"], earlier_rec["evidence_id"]}
    assert set(pairs) == {frozenset(p) for p in [(a, b) for a in copies for b in copies if a < b]}
    ordered = pairs[frozenset({later_rec["evidence_id"], earlier_rec["evidence_id"]})]
    assert str(ordered.earlier_observed) == earlier_rec["evidence_id"] and "claimed by the sources" in ordered.ordering_basis
    assert pairs[frozenset({uploaded["evidence_id"], later_rec["evidence_id"]})].earlier_observed is None  # an upload states no time
    assert all(r.status == "CANDIDATE" for r in rels)
    with db(api) as session:  # every MOC run supersedes the previous candidates instead of deleting them
        assert session.scalar(select(func.count()).select_from(MediaRelationship).where(MediaRelationship.superseded_at.is_not(None))) > 0
        with pytest.raises(Exception, match="not permitted"):
            session.execute(text("DELETE FROM media_relationships"))
        session.rollback()
        with pytest.raises(Exception, match="not permitted"):
            session.execute(text("UPDATE source_observations SET outcome = 'FAILED'"))


def test_refresh_appends_an_observation_and_bumps_the_revision(api, site):
    base, routes = site
    routes["/note.txt"] = (200, "text/plain", b"just text")
    case_id = new_case(api)
    source = api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/note.txt"}).json()["data"]
    drain(api)
    assert api.post(f"{API}/sources/{source['source_id']}/refresh").status_code == 202
    assert api.post(f"{API}/sources/{source['source_id']}/refresh").json()["error"]["code"] == "SOURCE_BUSY"
    drain(api)
    record = api.get(f"{API}/sources/{source['source_id']}").json()["data"]
    history = api.get(f"{API}/sources/{source['source_id']}/history").json()["data"]
    assert record["state"] == "METADATA_ONLY" and record["revision"] == 2 and [h["revision"] for h in history] == [1, 2]
    assert api.get(f"{API}/sources/{uuid.uuid4()}").json()["error"]["code"] == "SOURCE_NOT_FOUND"


def test_a_platform_url_is_recorded_as_unsupported_without_any_request(api):
    case_id = new_case(api)
    source = api.post(f"{API}/cases/{case_id}/sources", json={"url": "https://www.youtube.com/watch?v=abc"}).json()["data"]
    drain(api)
    record = api.get(f"{API}/sources/{source['source_id']}").json()["data"]
    assert (record["platform"], record["state"]) == ("YOUTUBE", "UNSUPPORTED") and "upload the media instead" in record["state_detail"]
    with db(api) as session:
        observation = session.scalars(select(SourceObservation)).one()
        assert observation.http_status is None and observation.redirects == []


def test_a_still_is_matched_to_the_frame_of_the_video_it_came_from(api, tmp_path, media):
    """A 4 s video showing an unrelated photo, then our photo from 2 s; the still is our photo."""
    from Backend.App.Utils.MediaProbe import resolve_executable

    ffmpeg = resolve_executable("ffmpeg")
    ours, other = tmp_path / "ours.png", tmp_path / "other.png"
    _photo().save(ours)
    Image.open(io.BytesIO(media["jpeg_exif"])).convert("RGB").resize((480, 360)).save(other)
    clip = tmp_path / "clip.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-loop", "1", "-t", "2", "-i", str(other), "-loop", "1", "-t", "2", "-i", str(ours),
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1,fps=25,format=yuv420p[v]", "-map", "[v]", "-c:v", "libx264", str(clip)], check=True)
    case_id = new_case(api)
    video = upload(api, case_id, clip.read_bytes(), "clip.mp4", "video/mp4")
    still = upload(api, case_id, _bytes(_photo(), "JPEG", quality=85), "still.jpg", "image/jpeg")
    drain(api)
    with db(api) as session:
        rels = session.scalars(select(MediaRelationship).where(MediaRelationship.superseded_at.is_(None))).all()
    assert [(r.kind, {str(r.evidence_a), str(r.evidence_b)}) for r in rels] == [("FRAME_OF_VIDEO", {video["evidence_id"], still["evidence_id"]})]
    assert rels[0].basis["frame_time_s"] >= 2.0  # found among the frames that show our photo
