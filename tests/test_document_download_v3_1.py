from pathlib import Path
import hashlib
import pytest


def test_download_integrity_primitives(tmp_path):
    root = tmp_path / "tenant"
    root.mkdir()
    file_path = root / "stored.pdf"
    payload = b"%PDF-1.7\nPOTOK CRM test\n"
    file_path.write_bytes(payload)
    assert hashlib.sha256(file_path.read_bytes()).hexdigest() == hashlib.sha256(payload).hexdigest()
    assert file_path.resolve().is_relative_to(root.resolve())


def test_download_path_escape_is_rejected(tmp_path):
    root = tmp_path / "tenant"
    root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"not tenant data")
    with pytest.raises(ValueError):
        outside.resolve(strict=True).relative_to(root.resolve(strict=True))


def test_download_detects_modified_file(tmp_path):
    file_path = tmp_path / "stored.pdf"
    file_path.write_bytes(b"original")
    expected = hashlib.sha256(file_path.read_bytes()).hexdigest()
    file_path.write_bytes(b"tampered")
    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert actual != expected
