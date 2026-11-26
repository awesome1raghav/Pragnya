"""The response envelopes from archive §9.1.

Success: {"success": true,  "message": ..., "data": ..., "meta": {"request_id", "timestamp"}}
Error:   {"success": false, "error": {"code", "message", "details"}, "meta": {...}}
"""

from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from Backend.App.Core.RequestContext import get_request_id

DataT = TypeVar("DataT")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Meta(BaseModel):
    request_id: str = Field(default_factory=get_request_id)
    timestamp: str = Field(default_factory=utc_now_iso)


class SuccessEnvelope(BaseModel, Generic[DataT]):
    success: Literal[True] = True
    message: str
    data: DataT
    meta: Meta = Field(default_factory=Meta)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorEnvelope(BaseModel):
    success: Literal[False] = False
    error: ErrorBody
    meta: Meta = Field(default_factory=Meta)


def envelope(data: DataT, message: str) -> SuccessEnvelope[DataT]:
    return SuccessEnvelope[DataT](message=message, data=data)
