"""Pure functions in acquisition and storage. No database or files beyond tmp_path."""

import uuid

import pytest

from Backend.App.Modules.NexCap.FileAcquisition import safe_display_filename
from Backend.App.Modules.NexCap.Validation import sniff_signature
from Backend.App.Schemas.Pagination import PaginationInfo
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Storage.StorageInterface import StorageError, original_key


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\xff\xd8\xff\xe0", ("image", "JPEG")),
        (b"\x89PNG\r\n\x1a\n", ("image", "PNG")),
        (b"GIF89a", ("image", "GIF")),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", ("image", "WEBP")),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", ("av", "wav")),
        (b"\x00\x00\x00\x18ftypisom", ("av", "mp4")),
        (b"\x00\x00\x00\x14ftypqt  ", ("av", "mov")),
        (b"\x00\x00\x00\x18ftypheic", None),
        (b"\x1a\x45\xdf\xa3", ("av", "matroska")),
        (b"ID3\x04", ("av", "mp3")),
        (b"\xff\xf1\x50\x80", ("av", "aac")),
        (b"fLaC", ("av", "flac")),
        (b"<html><script>", None),
        (b"%PDF-1.7", None),
        (b"", None),
    ],
)
def test_signature_sniffing(head, expected):
    assert sniff_signature(head) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("photo.png", "photo.png"),
        ("C:\\Users\\x\\photo.png", "photo.png"),
        ("../../etc/passwd", "passwd"),
        ("bad\x00name\x1f.png", "badname.png"),
        ("  spaced   name .png  ", "spaced name .png"),
        ("", "unnamed"),
        ("...", "unnamed"),
        ("a" * 300 + ".png", "a" * 255),
    ],
)
def test_display_filename_is_sanitised(raw, expected):
    assert safe_display_filename(raw) == expected


def test_storage_rejects_keys_it_did_not_build(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.ensure_layout()
    for key in ("../secret", "Originals/../../x", "Originals/a/b", f"Temporary/{uuid.uuid4()}/{uuid.uuid4()}"):
        with pytest.raises(StorageError):
            storage.local_path(key)
    assert storage.local_path(original_key(uuid.uuid4(), uuid.uuid4())) is not None


def test_storage_never_overwrites_an_original(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.ensure_layout()
    key = original_key(uuid.uuid4(), uuid.uuid4())
    first = storage.new_staging_path()
    first.write_bytes(b"original")
    storage.promote_original(first, key)
    second = storage.new_staging_path()
    second.write_bytes(b"replacement")
    with pytest.raises(StorageError):
        storage.promote_original(second, key)
    with storage.open_original(key) as handle:
        assert handle.read() == b"original"


def test_pagination_arithmetic():
    assert PaginationInfo.build(page=1, page_size=20, total_items=0).model_dump() == {
        "page": 1, "page_size": 20, "total_items": 0, "total_pages": 0, "has_next": False, "has_previous": False
    }
    assert PaginationInfo.build(page=2, page_size=20, total_items=41).model_dump() == {
        "page": 2, "page_size": 20, "total_items": 41, "total_pages": 3, "has_next": True, "has_previous": True
    }
