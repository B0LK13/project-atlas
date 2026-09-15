"""AT3-013 — PR/commit/test/build nodes from the Atlas 3 ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.engineering_nodes import PACKAGE_ID, compile_engineering_nodes
from project_atlas.atlas3.ledger import append_event


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_engineering_nodes(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_empty_ledger_stays_unknown(tmp_path: Path) -> None:
    report = compile_engineering_nodes(_vault(tmp_path), "harbor-api")
    assert report["package"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["reason"] == "NO_LEDGER_EVENTS"
    assert report["invented_from_git"] is False
    assert report["graph_is_authority"] is False
    assert report["promoted_to_truth_core"] == 0


def test_ledger_events_project_to_nodes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(vault, "harbor-api", kind="commit", summary="landed fix", subject_id="abc123")
    append_event(vault, "harbor-api", kind="pr", summary="opened review", subject_id="pr-9")
    append_event(vault, "harbor-api", kind="test", summary="unit pass", subject_id="job-1")
    append_event(vault, "harbor-api", kind="build", summary="image built", subject_id="bld-1")
    report = compile_engineering_nodes(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"commit": 1, "pr": 1, "test": 1, "build": 1}
    assert {node["node_type"] for node in report["nodes"]} == {"commit", "pr", "test", "build"}
    assert all(node["authority"] == "derived" for node in report["nodes"])
    assert all(node["evidence_refs"] for node in report["nodes"])


def test_non_mapped_events_do_not_invent_nodes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(vault, "harbor-api", kind="decision", summary="keep postgres 15")
    report = compile_engineering_nodes(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["nodes"] == []


def test_corrupt_ledger_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / "generated" / "ops" / "atlas3" / "ledger" / "harbor-api.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_engineering_nodes(vault, "harbor-api")
    assert exc.value.code == "LEDGER_CORRUPT"


def test_cli_nodes_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["ledger", "nodes", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert payload["package"] == PACKAGE_ID
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["ledger", "nodes", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "git history" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_touch_2x_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/engineering_nodes.py").read_text(encoding="utf-8")
    for name in (
        "chatgpt_bridge",
        "knowledge_compiler",
        "from project_atlas.ingestion",
        "write_text(",
        "write_json_atomic",
        "subprocess",
    ):
        assert name not in source
