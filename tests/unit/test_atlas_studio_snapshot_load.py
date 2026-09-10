"""Byte-accurate JSON snapshot loading."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio.snapshot_load import (  # noqa: E402
    CORRUPT_JSON,
    EMPTY,
    MISSING,
    NOT_OBJECT,
    load_json_snapshot,
)


def test_hash_is_of_exact_bytes_parsed(tmp_path: Path):
    path = tmp_path / "x.json"
    raw = b'{"a": 1, "b":2}'
    path.write_bytes(raw)
    snap = load_json_snapshot(path)
    assert snap.ok
    assert snap.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert snap.data == {"a": 1, "b": 2}


def test_corrupt_and_missing(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"{not json")
    snap = load_json_snapshot(bad)
    assert snap.error == CORRUPT_JSON
    assert snap.raw_sha256 == hashlib.sha256(b"{not json").hexdigest()
    assert load_json_snapshot(tmp_path / "nope.json").error == MISSING


def test_empty_file(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_bytes(b"")
    snap = load_json_snapshot(path)
    assert snap.error == EMPTY
    assert snap.raw_sha256 == hashlib.sha256(b"").hexdigest()
    assert snap.byte_length == 0


def test_non_utf8_bytes(tmp_path: Path):
    path = tmp_path / "bin.json"
    raw = b"\xff\xfe{\x00"
    path.write_bytes(raw)
    snap = load_json_snapshot(path)
    assert snap.error == CORRUPT_JSON
    assert snap.raw_sha256 == hashlib.sha256(raw).hexdigest()


def test_json_array_is_not_object(tmp_path: Path):
    path = tmp_path / "arr.json"
    path.write_text("[1, 2]", encoding="utf-8")
    snap = load_json_snapshot(path)
    assert snap.error == NOT_OBJECT


def test_no_second_read_drift(tmp_path: Path):
    """Hash and parse share one buffer — mutating file after load does not affect snap."""
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"v": 1}), encoding="utf-8")
    snap = load_json_snapshot(path)
    path.write_text(json.dumps({"v": 2}), encoding="utf-8")
    assert snap.data == {"v": 1}


def _deny_read(path: Path) -> bool:
    """Best-effort make `path` unreadable; report whether it actually worked.

    POSIX mode bits do not deny read access on Windows (and do not deny it to
    root on POSIX either), so the caller must MEASURE the result rather than
    assume the simulation took effect.
    """
    try:
        path.chmod(0)
    except OSError:
        return False
    try:
        path.read_bytes()
    except OSError:
        return True
    return False


def test_unreadable_file(tmp_path: Path):
    from atlas_studio.snapshot_load import READ_ERROR

    path = tmp_path / "locked.json"
    path.write_text("{}", encoding="utf-8")
    try:
        if not _deny_read(path):
            pytest.skip("cannot make a file unreadable on this platform/user")
        snap = load_json_snapshot(path)
        assert snap.error == READ_ERROR
    finally:
        path.chmod(0o644)


def test_read_error_surfaces_on_oserror(monkeypatch, tmp_path: Path):
    """Platform-neutral proof of the READ_ERROR branch.

    Does not depend on filesystem permissions, so it runs on Windows and as
    root, where `chmod(0)` cannot deny a read.
    """
    from atlas_studio.snapshot_load import READ_ERROR

    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")

    def boom(self, *a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", boom)
    snap = load_json_snapshot(path)
    assert snap.error == READ_ERROR
    assert snap.data is None
    assert snap.raw_sha256 is None
