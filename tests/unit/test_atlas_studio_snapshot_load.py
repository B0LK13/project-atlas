"""Byte-accurate JSON snapshot loading."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio.snapshot_load import (  # noqa: E402
    CORRUPT_JSON,
    MISSING,
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


def test_no_second_read_drift(tmp_path: Path):
    """Hash and parse share one buffer — mutating file after load does not affect snap."""
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"v": 1}), encoding="utf-8")
    snap = load_json_snapshot(path)
    path.write_text(json.dumps({"v": 2}), encoding="utf-8")
    assert snap.data == {"v": 1}
