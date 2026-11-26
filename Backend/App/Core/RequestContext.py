"""Per-request context shared by middleware, handlers and the response envelope."""

import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

# A client may supply its own ID to correlate logs; anything unusual is replaced.
_ACCEPTED_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def accept_or_create_request_id(candidate: str | None) -> str:
    if candidate and _ACCEPTED_REQUEST_ID.fullmatch(candidate):
        return candidate
    return new_request_id()


def set_request_id(request_id: str):
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    """The current request's ID; outside a request a fresh one is issued."""
    return _request_id.get() or new_request_id()
