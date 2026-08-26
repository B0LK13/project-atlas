"""AT3-011 — isolated file / symbol graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.file_graph import PACKAGE_ID, compile_file_graph


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "file-graph" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_file_graph(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_file_graph(_vault(tmp_path), "harbor-api")
    assert report["package"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["reason"] == "NO_DECLARED_FILE_GRAPH"
    assert report["walked_host_tree"] is False
    assert report["graph_is_authority"] is False
    assert report["promoted_to_truth_core"] == 0


def test_declared_files_and_symbols(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "files": [{"path": "src/api.py", "evidence_refs": ["src:src/api.py"]}],
            "symbols": [
                {
                    "name": "handle_request",
                    "file_path": "src/api.py",
                    "evidence_refs": ["src:src/api.py#handle_request"],
                }
            ],
        },
    )
    report = compile_file_graph(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"] == {"files": 1, "symbols": 1}
    assert report["files"][0]["path"] == "src/api.py"
    assert report["symbols"][0]["name"] == "handle_request"


def test_path_traversal_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"project_id": "harbor-api", "files": [{"path": "../secret", "evidence_refs": ["x"]}]},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_file_graph(vault, "harbor-api")
    assert exc.value.code == "UNSAFE_PATH"


def test_cross_project_and_corrupt_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign", "files": []})
    with pytest.raises(Atlas3Error) as cross:
        compile_file_graph(vault, "harbor-api")
    assert cross.value.code == "CROSS_PROJECT"
    path = vault / "generated" / "ops" / "atlas3" / "file-graph" / "harbor-api" / "declared.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(Atlas3Error) as corrupt:
        compile_file_graph(vault, "harbor-api")
    assert corrupt.value.code == "FILE_GRAPH_CORRUPT"


def test_authority_claim_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "harbor-api", "authentic_pilot": True})
    with pytest.raises(Atlas3Error) as exc:
        compile_file_graph(vault, "harbor-api")
    assert exc.value.code == "FILE_GRAPH_AUTHORITY_CLAIMED"


def test_cli_file_graph_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["file-graph", "--vault", str(vault), "--project", "harbor-api"])
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["status"] == "UNKNOWN"
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["file-graph", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "host trees" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_walk_or_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/file_graph.py").read_text(encoding="utf-8")
    for name in (
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "rglob(",
        "os.walk",
        "write_text(",
        "write_json_atomic",
    ):
        assert name not in source
