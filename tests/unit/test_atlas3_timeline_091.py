"""AT3-091 — isolated Timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.ledger import append_event
from project_atlas.atlas3.timeline import PACKAGE_ID, compile_timeline


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_empty_ledger_is_unknown(tmp_path: Path) -> None:
    report = compile_timeline(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["wall_clock_is_valid_time"] is False
    assert report["timeline_is_authority"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_orders_by_declared_valid_time(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        kind="commit",
        summary="later",
        valid_from="2026-08-02",
    )
    append_event(
        vault,
        "harbor-api",
        kind="commit",
        summary="earlier",
        valid_from="2026-08-01",
    )
    report = compile_timeline(vault, "harbor-api")
    assert report["status"] == "derived"
    assert [item["summary"] for item in report["entries"]] == ["earlier", "later"]
    assert all(item["wall_clock_is_valid_time"] is False for item in report["entries"])


def test_wall_clock_flag_fails_closed() -> None:
    from project_atlas.atlas3.timeline import _valid_key

    with pytest.raises(Atlas3Error) as exc:
        _valid_key({"wall_clock_is_valid_time": True, "valid_from": "2026-08-01"})
    assert exc.value.code == "WALL_CLOCK_AS_VALID_TIME"


def test_cli_timeline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["timeline", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert payload["timeline_is_authority"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["timeline", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "not valid-time" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/timeline.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
    ):
        assert name not in source
