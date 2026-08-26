"""AT3-021 — isolated derived relationship expansion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.rel_expand import PACKAGE_ID, expand_relationships


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "rel-expand" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        expand_relationships(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = expand_relationships(_vault(tmp_path), "harbor-api")
    assert report["package"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["graph_is_authority"] is False
    assert report["writes_as_graph_003"] is False
    assert report["promoted_to_truth_core"] == 0


def test_expands_graph_reuse_alias(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "relationships": [
                {
                    "relationship": "DEPENDS_ON",
                    "from_id": "api",
                    "to_id": "db",
                    "evidence_refs": ["doc:compose.yml#db"],
                },
                {
                    "relationship": "CONTRADICTS",
                    "from_id": "claim-16",
                    "to_id": "claim-15",
                    "evidence_refs": ["doc:adr.md#pg"],
                },
            ],
        },
    )
    report = expand_relationships(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"]["relationships"] == 2
    assert report["counts"]["expanded"] == 2
    depends = report["relationships"][0]
    assert depends["graph_alias"] == "depends-on"
    assert depends["winner"] is None
    contradicts = report["relationships"][1]
    assert contradicts["graph_alias"] == "conflicts-with"
    assert contradicts["winner"] is None


def test_winner_and_authority_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "relationships": [
                {
                    "relationship": "CONTRADICTS",
                    "from_id": "a",
                    "to_id": "b",
                    "evidence_refs": ["doc:x"],
                    "winner": "a",
                }
            ],
        },
    )
    with pytest.raises(Atlas3Error) as winner:
        expand_relationships(vault, "harbor-api")
    assert winner.value.code == "GRAPH_WINNER_CLAIMED"
    _write_declared(vault, {"project_id": "harbor-api", "graph_is_authority": True})
    with pytest.raises(Atlas3Error) as claimed:
        expand_relationships(vault, "harbor-api")
    assert claimed.value.code == "GRAPH_AUTHORITY_CLAIMED"


def test_cross_project_and_unknown_rel_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign"})
    with pytest.raises(Atlas3Error) as cross:
        expand_relationships(vault, "harbor-api")
    assert cross.value.code == "CROSS_PROJECT"
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "relationships": [
                {
                    "relationship": "WINS",
                    "from_id": "a",
                    "to_id": "b",
                    "evidence_refs": ["doc:x"],
                }
            ],
        },
    )
    with pytest.raises(Atlas3Error) as unknown:
        expand_relationships(vault, "harbor-api")
    assert unknown.value.code == "UNKNOWN_TWIN_RELATIONSHIP"


def test_cli_rel_expand_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(["rel-expand", "--vault", str(vault), "--project", "harbor-api"])
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
        parser.parse_args(["rel-expand", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "graph is not authority" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write_graph_store() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/rel_expand.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.graph_relationships",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "write_text(",
        "write_json_atomic",
    ):
        assert name not in source
