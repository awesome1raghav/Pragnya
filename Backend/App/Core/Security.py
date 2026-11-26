"""Browser-facing protections for a local, unauthenticated API (Step 9).

CORS only decides which origins may *read* responses. Without this guard, any web page open in the operator's browser
could still send a cross-site multipart form POST (a "simple" request, no preflight) and upload files into a case.
OriginGuardMiddleware refuses state-changing HTTP requests whose Origin header names a site outside CORS_ORIGINS
(403 ORIGIN_NOT_ALLOWED). Requests without an Origin header (curl, scripts, server-side tools) are not browser
cross-site requests and pass. WebSockets check their Origin in Api/V1/Realtime.py.

SecurityHeadersMiddleware adds headers to every HTTP response: nosniff, no framing, no referrer, same-site resource
policy, and `Cache-Control: no-store` on API JSON (case data should not sit in shared caches).

RateLimitMiddleware bounds state-changing requests per client (429 RATE_LIMITED), so a runaway script cannot flood the
job queue or storage. Reads are not limited.
"""

import time
from collections import defaultdict, deque

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from Backend.App.Core.Exceptions import ErrorCode, error_response

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k.lower() == name:
            return v.decode("latin-1")
    return None


class OriginGuardMiddleware:
    def __init__(self, app: ASGIApp, *, allowed: list[str]) -> None:
        self.app = app
        self.allowed = {o.rstrip("/").lower() for o in allowed}

    def _foreign(self, scope: Scope) -> bool:
        origin = _header(scope, b"origin")
        return origin is not None and origin.rstrip("/").lower() not in self.allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in MUTATING and self._foreign(scope):
            response = error_response(403, ErrorCode.ORIGIN_NOT_ALLOWED, "Requests from this site are not allowed",
                                      {"origin": _header(scope, b"origin")})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                h.setdefault("X-Content-Type-Options", "nosniff")
                h.setdefault("X-Frame-Options", "DENY")
                h.setdefault("Referrer-Policy", "no-referrer")
                h.setdefault("Cross-Origin-Resource-Policy", "same-site")
                if h.get("content-type", "").startswith("application/json"):
                    h.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, with_headers)


class RateLimitMiddleware:
    """Sliding one-minute window of state-changing requests per client address. 0 disables it."""

    def __init__(self, app: ASGIApp, *, per_minute: int, clock=time.monotonic) -> None:
        self.app, self.per_minute, self.clock = app, per_minute, clock
        self.seen: dict[str, deque] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.per_minute <= 0 or scope["type"] != "http" or scope["method"] not in MUTATING:
            await self.app(scope, receive, send)
            return
        client = (scope.get("client") or ("unknown", 0))[0]
        now, window = self.clock(), self.seen[client]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.per_minute:
            retry = max(1, int(60 - (now - window[0])) + 1)
            response = error_response(429, ErrorCode.RATE_LIMITED, "Too many changes from this client; try again shortly",
                                      {"limit_per_minute": self.per_minute, "retry_after_seconds": retry})
            response.headers["Retry-After"] = str(retry)
            await response(scope, receive, send)
            return
        window.append(now)
        await self.app(scope, receive, send)
