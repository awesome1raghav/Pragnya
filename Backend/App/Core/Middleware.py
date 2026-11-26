"""ASGI middleware that gives every HTTP request an ID and returns it as X-Request-ID."""

import logging

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from Backend.App.Core.Exceptions import ErrorCode, error_response
from Backend.App.Core.RequestContext import (
    REQUEST_ID_HEADER,
    accept_or_create_request_id,
    reset_request_id,
    set_request_id,
)

logger = logging.getLogger("nextron.api")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name.decode("latin-1").lower() == REQUEST_ID_HEADER.lower():
                incoming = value.decode("latin-1")
                break
        request_id = accept_or_create_request_id(incoming)
        scope.setdefault("state", {})["request_id"] = request_id
        token = set_request_id(request_id)

        response_started = False

        async def send_with_header(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        except Exception as exc:
            # Handled here rather than by Starlette's outermost error middleware, so the
            # 500 envelope carries the same request ID as the log line and the header.
            if scope["type"] != "http" or response_started:
                raise
            logger.exception("Unhandled error on request %s", request_id, exc_info=exc)
            response = error_response(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred")
            await response(scope, receive, send_with_header)
        finally:
            reset_request_id(token)
