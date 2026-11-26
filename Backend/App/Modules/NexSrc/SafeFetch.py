"""Server-side retrieval of an investigator-supplied URL without server-side request forgery (archive §17.3).

Rules, applied to the first request and to every redirect hop:
  * http and https only; no credentials in the URL; at most 2,048 characters;
  * the host name is resolved once, and **every** address it resolves to must be globally routable
    (`ipaddress.is_global`): loopback, private, link-local (including cloud metadata 169.254.169.254), carrier-grade
    NAT, multicast, reserved and unspecified addresses are refused, in any spelling (decimal, octal, short forms and
    IPv4-mapped IPv6 are all normalised by the resolver first);
  * the connection is made to the address that was checked (the request is pinned to it; TLS still verifies the
    certificate for the host name), so a DNS answer cannot change between the check and the connection;
  * at most 5 redirects, a byte limit enforced while streaming, and connect/read time limits.
Nothing is followed automatically: the caller sees every hop.
"""

import hashlib
import ipaddress
import socket
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import certifi
import urllib3

USER_AGENT = "NEXTRON-SourceRetrieval/1 (forensic evidence acquisition; contact: operator of this instance)"
MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 5
TRACKING_PARAMETERS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid")


class Refused(Exception):
    """The URL or an address it resolves to may not be fetched."""


class FetchError(Exception):
    """The fetch could not complete (network error, timeout, too large)."""


@dataclass
class Hop:
    url: str
    address: str | None = None
    status: int | None = None


@dataclass
class FetchResult:
    final_url: str
    status: int
    content_type: str | None
    size: int
    sha256: str
    path: Path | None              # streamed body (when a destination was given)
    body: bytes | None             # small bodies kept in memory (when no destination)
    hops: list[Hop] = field(default_factory=list)


def normalize(raw: str) -> str:
    """A canonical form of a URL: scheme and host lower-cased, IDNA host, default port and fragment dropped,
    tracking parameters removed. Raises Refused for what may never be fetched."""
    text = (raw or "").strip()
    if not text:
        raise Refused("The URL is empty")
    if len(text) > MAX_URL_LENGTH:
        raise Refused(f"The URL is longer than {MAX_URL_LENGTH} characters")
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise Refused(f"Only http and https URLs can be retrieved (got {scheme or 'none'})")
    if parts.username or parts.password or "@" in parts.netloc:
        raise Refused("URLs with credentials are not retrieved")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise Refused("The URL has no host")
    try:
        host = host.encode("idna").decode("ascii").lower() if not _is_ip_literal(host) else host.lower()
    except UnicodeError as exc:
        raise Refused("The host name is not valid") from exc
    port = parts.port
    if port is not None and port == {"http": 80, "https": 443}[scheme]:
        port = None
    netloc = (f"[{host}]" if ":" in host else host) + (f":{port}" if port else "")
    query = "&".join(p for p in parts.query.split("&") if p and p.split("=", 1)[0].lower() not in TRACKING_PARAMETERS)
    return urlunsplit((scheme, netloc, parts.path or "/", query, ""))


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _check(address: str) -> None:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast or ip.is_reserved:  # Python counts multicast as "global"; refuse it explicitly
        raise Refused(f"The URL resolves to a non-public address ({ip}); NEXTRON does not fetch internal addresses")


def numeric_ipv4(host: str) -> str | None:
    """The address a numeric IPv4 spelling stands for, as inet_aton reads it ("2130706433", "0x7f000001", "0177.0.0.1",
    "127.1"), or None when the host is a name. Parsed here so the rule does not depend on the platform's resolver."""
    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    values = []
    for part in parts:
        try:
            values.append(int(part, 16) if part.lower().startswith("0x") else int(part, 8) if part.startswith("0") and part != "0" else int(part, 10))
        except ValueError:
            return None
    limits = {1: [2**32], 2: [2**8, 2**24], 3: [2**8, 2**8, 2**16], 4: [2**8] * 4}[len(values)]
    if any(v < 0 or v >= limit for v, limit in zip(values, limits)):
        return None
    number = 0
    for v, limit in zip(values, limits):
        number = number * limit + v
    return str(ipaddress.IPv4Address(number))


def resolve(host: str, port: int, *, allow: frozenset[str] = frozenset()) -> str:
    """The first resolved address, after checking that every address the host resolves to is public."""
    literal = numeric_ipv4(host)
    if literal is not None:
        if literal not in allow:
            _check(literal)
        return literal
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"The host name could not be resolved: {host}") from exc
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise FetchError(f"The host name has no addresses: {host}")
    for address in addresses:
        if address not in allow:
            _check(address)
    return addresses[0]


def fetch(url: str, *, max_bytes: int, timeout: float, destination: Path | None = None,
          allow: frozenset[str] = frozenset()) -> FetchResult:
    """GET `url` under the rules above. `allow` exempts exact addresses from the public-address rule; only tests pass it."""
    hops: list[Hop] = []
    current = normalize(url)
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        scheme, host = parts.scheme, parts.hostname
        port = parts.port or (443 if scheme == "https" else 80)
        hop = Hop(current)
        hops.append(hop)
        hop.address = resolve(host, port, allow=allow)
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        headers = {"Host": parts.netloc, "User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"}
        limits = urllib3.Timeout(connect=min(10.0, timeout), read=timeout)
        if scheme == "https":
            pool = urllib3.HTTPSConnectionPool(hop.address, port, server_hostname=host, assert_hostname=host,
                                               cert_reqs="CERT_REQUIRED", ca_certs=certifi.where(), timeout=limits, retries=False)
        else:
            pool = urllib3.HTTPConnectionPool(hop.address, port, timeout=limits, retries=False)
        try:
            response = pool.urlopen("GET", target, headers=headers, redirect=False, preload_content=False, retries=False)
        except urllib3.exceptions.HTTPError as exc:
            raise FetchError(f"{type(exc).__name__}: {exc}"[:300]) from exc
        hop.status = response.status
        if response.status in (301, 302, 303, 307, 308) and response.headers.get("Location"):
            response.release_conn()
            current = normalize(urljoin(current, response.headers["Location"]))
            continue
        return _body(response, current, hops, max_bytes=max_bytes, destination=destination)
    raise FetchError(f"More than {MAX_REDIRECTS} redirects")


def _body(response, url: str, hops: list[Hop], *, max_bytes: int, destination: Path | None) -> FetchResult:
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        response.release_conn()
        raise FetchError(f"The response is larger than the limit ({int(declared)} > {max_bytes} bytes)")
    digest, size, chunks = hashlib.sha256(), 0, []
    sink = open(destination, "xb") if destination is not None else None  # noqa: SIM115 — closed below
    try:
        for chunk in response.stream(64 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise FetchError(f"The response is larger than the limit ({max_bytes} bytes)")
            digest.update(chunk)
            if sink is not None:
                sink.write(chunk)
            else:
                chunks.append(chunk)
    except urllib3.exceptions.HTTPError as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}"[:300]) from exc
    finally:
        if sink is not None:
            sink.close()
        response.release_conn()
    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower() or None
    return FetchResult(url, response.status, content_type, size, digest.hexdigest(), destination,
                       None if sink is not None else b"".join(chunks), hops)
