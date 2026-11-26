"""NEX-SRC connectors: what NEXTRON may retrieve from a source URL, and how (archive §4 module 09, §17).

  generic    any public http(s) URL: a direct media file is retrieved as is; an HTML page is read for its declared
             metadata (title, Open Graph / Twitter card media, claimed publication time) and the media it declares
             is retrieved through the same safe fetcher. Nothing is executed (no JavaScript, no rendering).
  platforms  YouTube, X, Instagram, Facebook, TikTok and WhatsApp need an approved API connector and credentials
             for their content. None is configured, so those URLs end UNSUPPORTED with that reason: NEXTRON does
             not scrape platforms or work around their access rules. The investigator uploads the media instead.
"""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from Backend.App.Modules.NexSrc import SafeFetch

MAX_HTML_BYTES = 2 * 1024 * 1024
MEDIA_PREFIXES = ("image/", "video/", "audio/")

_PLATFORM_HOSTS = {
    "YOUTUBE": ("youtube.com", "youtu.be"), "X": ("x.com", "twitter.com", "t.co"), "INSTAGRAM": ("instagram.com",),
    "FACEBOOK": ("facebook.com", "fb.watch", "fb.com"), "TIKTOK": ("tiktok.com",), "WHATSAPP": ("whatsapp.com", "wa.me"),
}


def platform_of(normalized_url: str) -> str:
    host = urlsplit(normalized_url).hostname or ""
    for platform, domains in _PLATFORM_HOSTS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return "GENERIC"


@dataclass
class Retrieval:
    outcome: str                       # a SOURCE_STATES value
    detail: str
    connector: str
    final_url: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    bytes_received: int | None = None
    media_path: Path | None = None     # staged media to preserve, when retrieved
    media_sha256: str | None = None
    media_size: int | None = None
    media_url: str | None = None
    hops: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class _MetaParser(HTMLParser):
    KEYS = {"og:title", "og:description", "og:image", "og:image:url", "og:image:secure_url", "og:video", "og:video:url",
            "og:video:secure_url", "og:audio", "og:audio:url", "og:site_name", "og:url", "article:published_time",
            "article:modified_time", "og:updated_time", "twitter:image", "twitter:player:stream", "datePublished", "date"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key in self.KEYS and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()[:2000]
        elif tag == "title":
            self._in_title = True
        elif tag == "time" and a.get("datetime") and "time:datetime" not in self.meta:
            self.meta["time:datetime"] = a["datetime"][:64]

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and self.title is None and data.strip():
            self.title = re.sub(r"\s+", " ", data.strip())[:500]


def _hops(result_or_hops) -> list[dict]:
    hops = result_or_hops.hops if hasattr(result_or_hops, "hops") else result_or_hops
    return [{"url": h.url, "address": h.address, "status": h.status} for h in hops]


def _http_outcome(status: int) -> tuple[str, str] | None:
    if status in (401, 403, 451):
        return "RESTRICTED", f"The source refused access (HTTP {status}); NEXTRON does not work around access controls"
    if status in (404, 410):
        return "NOT_FOUND", f"The source answered HTTP {status}: the content is not there (removed, moved or never existed)"
    if status == 429:
        return "RATE_LIMITED", "The source is rate-limiting requests (HTTP 429); try again later"
    if status >= 400:
        return "UNAVAILABLE", f"The source answered HTTP {status}"
    return None


def retrieve(normalized_url: str, staging: Path, *, max_bytes: int, timeout: float, allow: frozenset[str] = frozenset()) -> Retrieval:
    platform = platform_of(normalized_url)
    if platform != "GENERIC":
        return Retrieval("UNSUPPORTED", f"{platform.title()} content needs an approved platform API connector, which is not "
                                        "configured. NEXTRON does not scrape platforms; upload the media instead.", platform.lower())
    try:
        page = SafeFetch.fetch(normalized_url, max_bytes=max_bytes, timeout=timeout, destination=staging, allow=allow)
    except SafeFetch.Refused as exc:
        return Retrieval("BLOCKED", str(exc), "generic")
    except SafeFetch.FetchError as exc:
        return Retrieval("UNAVAILABLE", str(exc), "generic")
    base = dict(connector="generic", final_url=page.final_url, http_status=page.status, content_type=page.content_type,
                bytes_received=page.size, hops=_hops(page))
    bad = _http_outcome(page.status)
    if bad:
        staging.unlink(missing_ok=True)
        return Retrieval(*bad, **base)
    if page.content_type and page.content_type.startswith(MEDIA_PREFIXES):
        return Retrieval("RETRIEVED", f"Retrieved {page.content_type} directly", **base, media_path=staging,
                         media_sha256=page.sha256, media_size=page.size, media_url=page.final_url)
    if page.content_type not in ("text/html", "application/xhtml+xml"):
        staging.unlink(missing_ok=True)
        return Retrieval("METADATA_ONLY", f"The URL returned {page.content_type or 'no content type'}, which is neither media nor a web page", **base)

    if page.size > MAX_HTML_BYTES:
        staging.unlink(missing_ok=True)
        return Retrieval("METADATA_ONLY", "The page is larger than 2 MB; its metadata was not read", **base)
    parser = _MetaParser()
    parser.feed(staging.read_bytes().decode("utf-8", "replace"))
    staging.unlink(missing_ok=True)
    meta = parser.meta
    metadata = {"title": meta.get("og:title") or parser.title, "site_name": meta.get("og:site_name"),
                "claimed_publication_time": meta.get("article:published_time") or meta.get("datePublished") or meta.get("time:datetime") or meta.get("date"),
                "claimed_modified_time": meta.get("article:modified_time") or meta.get("og:updated_time"), "declared": meta}
    media = next((meta[k] for k in ("og:video:secure_url", "og:video:url", "og:video", "twitter:player:stream", "og:audio:url", "og:audio",
                                    "og:image:secure_url", "og:image:url", "og:image", "twitter:image") if meta.get(k)), None)
    if not media:
        return Retrieval("METADATA_ONLY", "The page declares no media (no Open Graph or Twitter card media)", **base, metadata=metadata)
    media_url = urljoin(page.final_url, media)
    try:
        item = SafeFetch.fetch(media_url, max_bytes=max_bytes, timeout=timeout, destination=staging, allow=allow)
    except SafeFetch.Refused as exc:
        return Retrieval("BLOCKED", f"The page's declared media may not be fetched: {exc}", **base, metadata=metadata)
    except SafeFetch.FetchError as exc:
        return Retrieval("METADATA_ONLY", f"The page was read but its declared media could not be retrieved: {exc}", **base, metadata=metadata)
    base["hops"] += _hops(item)
    bad = _http_outcome(item.status)
    if bad or not (item.content_type or "").startswith(MEDIA_PREFIXES):
        staging.unlink(missing_ok=True)
        why = bad[1] if bad else f"it is {item.content_type or 'untyped'}, not media"
        return Retrieval("METADATA_ONLY", f"The page was read; its declared media was not retrieved: {why}", **base, metadata=metadata)
    return Retrieval("RETRIEVED", f"Retrieved the media the page declares ({item.content_type})", **base, media_path=staging,
                     media_sha256=item.sha256, media_size=item.size, media_url=item.final_url, metadata=metadata)
