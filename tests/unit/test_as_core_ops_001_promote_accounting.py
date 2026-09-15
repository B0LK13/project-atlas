"""AS-CORE-OPS-001 / CORE-OPS-001: hash-before-replace + promote accounting."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from project_atlas.ingestion import (
    PromoteAccounting,
    _file_hash,
    _payload_sha256,
    _promote,
    _replace_path,
)


def test_ops001_fr001_hash_match_skips_replace(tmp_path: Path) -> None:
    """OPS001-FR-001: identical SHA-256 skips canonical replace."""
    target = tmp_path / "canonical.txt"
    payload = b"stable-payload\n"
    target.write_bytes(payload)
    before_mtime = target.stat().st_mtime_ns
    before_inode = target.stat().st_ino

    with patch("project_atlas.ingestion._replace_path") as replace:
        result = _promote({target: payload})

    replace.assert_not_called()
    assert target.read_bytes() == payload
    assert target.stat().st_mtime_ns == before_mtime
    assert target.stat().st_ino == before_inode
    assert result == PromoteAccounting(planned=1, noop_skipped=1, written=0)


def test_ops001_fr001_hash_compare_not_byte_equality(tmp_path: Path) -> None:
    """OPS001-FR-001: skip decision uses sha256 helpers, not read_bytes ==."""
    target = tmp_path / "hashed.txt"
    payload = b"hash-path\n"
    target.write_bytes(payload)
    calls: list[str] = []

    def tracking_file_hash(path: Path) -> str:
        calls.append("file")
        return _file_hash(path)

    def tracking_payload(data: bytes) -> str:
        calls.append("payload")
        return _payload_sha256(data)

    with (
        patch("project_atlas.ingestion._file_hash", side_effect=tracking_file_hash),
        patch("project_atlas.ingestion._payload_sha256", side_effect=tracking_payload),
        patch("project_atlas.ingestion._replace_path") as replace,
    ):
        result = _promote({target: payload})

    assert "file" in calls and "payload" in calls
    replace.assert_not_called()
    assert result.noop_skipped == 1
    assert result.written == 0


def test_ops001_fr002_hash_mismatch_writes(tmp_path: Path) -> None:
    """OPS001-FR-002: digest mismatch stages and replaces."""
    target = tmp_path / "changed.txt"
    target.write_bytes(b"old\n")
    new_payload = b"new\n"

    result = _promote({target: new_payload})

    assert target.read_bytes() == new_payload
    assert result == PromoteAccounting(planned=1, noop_skipped=0, written=1)


def test_ops001_fr002_missing_target_writes(tmp_path: Path) -> None:
    """OPS001-FR-002: absent file is a write, not a noop."""
    target = tmp_path / "nested" / "fresh.txt"
    payload = b"created\n"

    result = _promote({target: payload})

    assert target.read_bytes() == payload
    assert result == PromoteAccounting(planned=1, noop_skipped=0, written=1)


def test_ops001_fr003_accounting_is_deterministic(tmp_path: Path) -> None:
    """OPS001-FR-003: mixed plan yields stable planned/noop/written counts."""
    same = tmp_path / "same.txt"
    same.write_bytes(b"unchanged\n")
    change = tmp_path / "change.txt"
    change.write_bytes(b"before\n")
    fresh = tmp_path / "fresh.txt"
    plan = {
        same: b"unchanged\n",
        change: b"after\n",
        fresh: b"new\n",
    }

    first = _promote(plan)
    second = _promote(plan)

    assert first == PromoteAccounting(planned=3, noop_skipped=1, written=2)
    assert second == PromoteAccounting(planned=3, noop_skipped=3, written=0)
    assert first._fields == ("planned", "noop_skipped", "written")
    assert not hasattr(first, "generated_at")
    assert not hasattr(first, "timestamp")


def test_ops001_fr003_empty_plan_zero_counts(tmp_path: Path) -> None:
    result = _promote({})
    assert result == PromoteAccounting(planned=0, noop_skipped=0, written=0)


def test_ops001_adv_directory_target_still_fail_closed(tmp_path: Path) -> None:
    """ADV: directory collision still aborts before accounting success."""
    target = tmp_path / "not-a-file"
    target.mkdir()
    with pytest.raises(IsADirectoryError):
        _promote({target: b"x\n"})


def test_ops001_adv_payload_sha256_matches_stdlib() -> None:
    payload = b"canonical-bytes\n"
    assert _payload_sha256(payload) == hashlib.sha256(payload).hexdigest()


def test_ops001_adv_noop_leaves_no_stage_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "clean.txt"
    target.write_bytes(b"clean\n")
    _promote({target: b"clean\n"})
    leftovers = [p for p in tmp_path.iterdir() if ".atlas-" in p.name]
    assert leftovers == []


def test_ops001_adv_write_then_noop_replay(tmp_path: Path) -> None:
    """ADV: second identical promote is pure noop accounting (zero writes)."""
    target = tmp_path / "replay.txt"
    payload = b"replay-stable\n"
    write = _promote({target: payload})
    noop = _promote({target: payload})
    assert write.written == 1 and write.noop_skipped == 0
    assert noop.written == 0 and noop.noop_skipped == 1
    assert target.read_bytes() == payload


def test_ops001_adv_replace_seam_still_used_on_write(tmp_path: Path) -> None:
    target = tmp_path / "seam.txt"
    target.write_bytes(b"a\n")
    observed: list[tuple[str, str]] = []

    def recording_replace(source: Path, destination: Path) -> None:
        observed.append((source.name, destination.name))
        os.replace(source, destination)

    with patch("project_atlas.ingestion._replace_path", side_effect=recording_replace):
        result = _promote({target: b"b\n"})

    assert result.written == 1
    assert observed  # staging/backup replace path still exercised
    assert target.read_bytes() == b"b\n"


def test_ops001_adv_accounting_type_is_module_level() -> None:
    """OPS001-FR-003: module-level result type, not ad-hoc dict."""
    assert issubclass(PromoteAccounting, tuple)
    sample = PromoteAccounting(planned=2, noop_skipped=1, written=1)
    as_dict: dict[str, Any] = sample._asdict()
    assert set(as_dict) == {"planned", "noop_skipped", "written"}


def test_replace_path_lost_race_is_noop_when_destination_exists(tmp_path: Path) -> None:
    destination = tmp_path / "authority.json"
    destination.write_text("winner\n", encoding="utf-8")
    missing = tmp_path / ".authority.json.lost.atlas-stage"
    _replace_path(missing, destination)
    assert destination.read_text(encoding="utf-8") == "winner\n"


def test_replace_path_missing_source_without_destination_fails(tmp_path: Path) -> None:
    missing = tmp_path / ".authority.json.lost.atlas-stage"
    destination = tmp_path / "authority.json"
    with pytest.raises(FileNotFoundError):
        _replace_path(missing, destination)
