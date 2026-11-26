"""NEX-CAP streaming multipart receiver.

The request body is parsed as it arrives: the file part goes straight to a staging file
while SHA-256 and size are computed, and the size limit is enforced mid-stream. Nothing is
buffered whole in memory, and no client-supplied name ever reaches the filesystem.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import ClientDisconnect, Request

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexEvd.HashService import StreamingDigest

MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_TEXT_FIELD_BYTES = 8 * 1024


@dataclass
class ReceivedUpload:
    staged_path: Path
    filename: str
    declared_content_type: str | None
    size_bytes: int
    sha256: str
    fields: dict[str, str] = field(default_factory=dict)


def safe_display_filename(raw: str | None) -> str:
    """The client's filename as a label only: basename, no control characters, bounded length."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in unicodedata.normalize("NFC", name) if unicodedata.category(ch)[0] != "C")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:255] or "unnamed"


class _Part:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.name: str | None = None
        self.filename: str | None = None
        self.content_type: str | None = None
        self.text = bytearray()
        self.is_file = False


async def receive_upload(
    request: Request,
    staged_path: Path,
    *,
    max_file_bytes: int,
    file_field: str,
    text_fields: frozenset[str],
) -> ReceivedUpload:
    content_type, params = parse_options_header(request.headers.get("content-type", ""))
    boundary = params.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise NextronError(415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Evidence must be sent as multipart/form-data")

    declared_length = request.headers.get("content-length")
    if declared_length and declared_length.isdigit() and int(declared_length) > max_file_bytes + MULTIPART_OVERHEAD_BYTES:
        raise _too_large(max_file_bytes)

    digest = StreamingDigest()
    fields: dict[str, str] = {}
    state: dict = {"part": None, "file": None, "file_seen": False, "filename": None, "declared": None, "header": [b"", b""]}

    def on_part_begin() -> None:
        state["part"] = _Part()

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state["header"][0] += data[start:end]

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state["header"][1] += data[start:end]

    def on_header_end() -> None:
        name, value = state["header"]
        state["part"].headers[name.decode("latin-1").lower()] = value.decode("utf-8", "replace")
        state["header"] = [b"", b""]

    def on_headers_finished() -> None:
        part: _Part = state["part"]
        _, disposition = parse_options_header(part.headers.get("content-disposition", ""))
        part.name = disposition.get(b"name", b"").decode("utf-8", "replace") or None
        raw_filename = disposition.get(b"filename")
        part.content_type = part.headers.get("content-type")
        if part.name == file_field and raw_filename is not None:
            if state["file_seen"]:
                raise NextronError(400, ErrorCode.INVALID_UPLOAD, "Exactly one file may be uploaded per request")
            part.is_file = True
            state["file_seen"] = True
            state["filename"] = raw_filename.decode("utf-8", "replace")
            state["declared"] = (part.content_type or "")[:255] or None
            state["file"] = open(staged_path, "xb")  # noqa: SIM115 — closed in on_part_end / finally
        elif part.name not in text_fields:
            raise NextronError(400, ErrorCode.INVALID_UPLOAD, f"Unexpected form field: {part.name!r}")

    def on_part_data(data: bytes, start: int, end: int) -> None:
        part: _Part = state["part"]
        chunk = data[start:end]
        if part.is_file:
            if digest.size + len(chunk) > max_file_bytes:
                raise _too_large(max_file_bytes)
            digest.update(chunk)
            state["file"].write(chunk)
        else:
            part.text.extend(chunk)
            if len(part.text) > MAX_TEXT_FIELD_BYTES:
                raise NextronError(400, ErrorCode.INVALID_UPLOAD, f"Form field {part.name!r} is too long")

    def on_part_end() -> None:
        part: _Part = state["part"]
        if part.is_file:
            file: BinaryIO = state["file"]
            file.flush()
            file.close()
            state["file"] = None
        else:
            try:
                fields[part.name] = part.text.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise NextronError(400, ErrorCode.INVALID_UPLOAD, f"Form field {part.name!r} is not UTF-8") from exc

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
        },
        max_size=max_file_bytes + MULTIPART_OVERHEAD_BYTES,
    )

    try:
        async for chunk in request.stream():
            parser.write(chunk)
        parser.finalize()
    except NextronError:
        raise
    except ClientDisconnect as exc:
        raise NextronError(400, ErrorCode.INVALID_UPLOAD, "The client disconnected before the upload finished") from exc
    except Exception as exc:  # malformed multipart framing from python-multipart
        raise NextronError(400, ErrorCode.INVALID_UPLOAD, "The multipart body is malformed") from exc
    finally:
        if state["file"] is not None:
            state["file"].close()

    if not state["file_seen"]:
        raise NextronError(400, ErrorCode.INVALID_UPLOAD, f"A file part named {file_field!r} is required")
    if digest.size == 0:
        raise NextronError(400, ErrorCode.INVALID_UPLOAD, "The uploaded file is empty")

    return ReceivedUpload(
        staged_path=staged_path,
        filename=safe_display_filename(state["filename"]),
        declared_content_type=state["declared"],
        size_bytes=digest.size,
        sha256=digest.hexdigest,
        fields=fields,
    )


def _too_large(limit: int) -> NextronError:
    return NextronError(413, ErrorCode.UPLOAD_TOO_LARGE, "The uploaded file exceeds the size limit", {"max_bytes": limit})
