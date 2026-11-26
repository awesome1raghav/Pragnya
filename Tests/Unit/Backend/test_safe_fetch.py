"""SSRF protection of source retrieval (Implementation Plan Step 5 "done when": SSRF tests). No network needed:
addresses are refused before any connection is made; the redirect tests use a local server in the test."""

import http.server
import threading

import pytest

from Backend.App.Modules.NexSrc import Connectors, SafeFetch


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/admin", "http://[::1]/", "http://0.0.0.0/", "http://10.0.0.5/", "http://172.16.3.4/",
    "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/", "http://100.64.0.1/", "http://[fe80::1]/",
    "http://2130706433/", "http://0x7f000001/", "http://0177.0.0.1/", "http://127.1/", "http://10.1/", "http://[::ffff:127.0.0.1]/",
    "http://224.0.0.1/", "http://240.0.0.1/",
])
def test_internal_addresses_are_refused_in_any_spelling(url):
    with pytest.raises(SafeFetch.Refused, match="non-public address"):
        SafeFetch.fetch(url, max_bytes=1000, timeout=2)


@pytest.mark.parametrize(("url", "why"), [
    ("file:///etc/passwd", "Only http and https"), ("ftp://example.org/x", "Only http and https"), ("gopher://example.org/", "Only http and https"),
    ("http://user:pass@example.org/", "credentials"), ("https://example.org@127.0.0.1/", "credentials"), ("", "empty"),
    ("https://" + "a" * 2100 + ".org/", "longer than"),
])
def test_unsafe_url_forms_are_refused(url, why):
    with pytest.raises(SafeFetch.Refused, match=why):
        SafeFetch.normalize(url)


def test_normalisation_is_canonical():
    assert SafeFetch.normalize("  HTTPS://Example.ORG:443/Path?utm_source=x&id=7#frag ") == "https://example.org/Path?id=7"
    assert SafeFetch.normalize("example.org") == "https://example.org/"
    assert SafeFetch.normalize("http://bücher.example/a") == "http://xn--bcher-kva.example/a"


@pytest.mark.parametrize(("url", "platform"), [
    ("https://www.youtube.com/watch?v=abc", "YOUTUBE"), ("https://youtu.be/abc", "YOUTUBE"), ("https://x.com/a/status/1", "X"),
    ("https://twitter.com/a", "X"), ("https://www.instagram.com/p/x/", "INSTAGRAM"), ("https://m.facebook.com/x", "FACEBOOK"),
    ("https://www.tiktok.com/@a/video/1", "TIKTOK"), ("https://news.example.org/a", "GENERIC"), ("https://notyoutube.com/", "GENERIC"),
])
def test_platform_detection(url, platform):
    assert Connectors.platform_of(SafeFetch.normalize(url)) == platform


def test_platform_urls_are_not_fetched(tmp_path):
    r = Connectors.retrieve(SafeFetch.normalize("https://www.instagram.com/p/abc/"), tmp_path / "x", max_bytes=1000, timeout=2)
    assert r.outcome == "UNSUPPORTED" and "does not scrape" in r.detail and not (tmp_path / "x").exists()


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802
        status, headers, body = self.routes.get(self.path, (404, {}, b"missing"))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Handler.routes
    httpd.shutdown()
    _Handler.routes = {}


def test_redirect_to_an_internal_address_is_refused(server):
    base, routes = server
    routes["/start"] = (302, {"Location": "http://169.254.169.254/latest/meta-data/"}, b"")
    with pytest.raises(SafeFetch.Refused, match="non-public"):
        SafeFetch.fetch(base + "/start", max_bytes=1000, timeout=5, allow=frozenset({"127.0.0.1"}))


def test_redirect_hops_are_recorded_and_limited(server):
    base, routes = server
    routes["/a"] = (301, {"Location": "/b"}, b"")
    routes["/b"] = (200, {"Content-Type": "text/plain"}, b"hello")
    r = SafeFetch.fetch(base + "/a", max_bytes=1000, timeout=5, allow=frozenset({"127.0.0.1"}))
    assert r.final_url.endswith("/b") and r.body == b"hello" and [h.status for h in r.hops] == [301, 200]
    for i in range(7):
        routes[f"/loop{i}"] = (302, {"Location": f"/loop{i + 1}"}, b"")
    with pytest.raises(SafeFetch.FetchError, match="redirects"):
        SafeFetch.fetch(base + "/loop0", max_bytes=1000, timeout=5, allow=frozenset({"127.0.0.1"}))


def test_size_limit_is_enforced_while_streaming(server):
    base, routes = server
    routes["/big"] = (200, {"Content-Type": "image/png"}, b"x" * 5000)
    with pytest.raises(SafeFetch.FetchError, match="larger than the limit"):
        SafeFetch.fetch(base + "/big", max_bytes=1000, timeout=5, allow=frozenset({"127.0.0.1"}))


@pytest.mark.parametrize(("host", "address"), [("2130706433", "127.0.0.1"), ("0x7f000001", "127.0.0.1"), ("0177.0.0.1", "127.0.0.1"),
                                               ("127.1", "127.0.0.1"), ("10.1", "10.0.0.1"), ("8.8.8.8", "8.8.8.8"), ("example.org", None), ("1.2.3.4.5", None)])
def test_numeric_ipv4_spellings_are_read_like_inet_aton(host, address):
    assert SafeFetch.numeric_ipv4(host) == address
