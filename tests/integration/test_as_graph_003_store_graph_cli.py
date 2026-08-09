"""AS-GRAPH-003 — CLI store-graph integration smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import main

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "graphify-present"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_for(root: Path) -> dict[str, object]:
    sources: list[dict[str, object]] = []
    for path in sorted((root / "graphify-out").iterdir(), key=lambda p: p.name.casefold()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        sources.append(
            {
                "source_id": f"source-{path.stem}",
                "path": relative,
                "media_type": "application/json",
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "classification_state": "unclassified",
                "authority": {"level": "derived"},
            }
        )
    return {"schema_version": 1, "project_id": "graphify-present", "sources": sources}


def test_store_graph_cli_write(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_for(FIXTURE), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    for relative in (
        "claims/claim.json",
        "relationships/nodes.json",
        "state/authoritative-state/x.json",
    ):
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"sentinel":true}\n', encoding="utf-8", newline="\n")

    code = main(
        [
            "store-graph",
            "--source",
            str(FIXTURE),
            "--manifest",
            str(manifest_path),
            "--vault",
            str(vault),
            "--write",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "authority: derived" in captured.out
    assert "retained:" in captured.out
    rel_dir = vault / "generated" / "graph" / "relationships" / "graphify-present"
    assert rel_dir.is_dir()
    assert list(rel_dir.glob("*.json"))
    for relative in (
        "claims/claim.json",
        "relationships/nodes.json",
        "state/authoritative-state/x.json",
    ):
        assert (vault / relative).read_text(encoding="utf-8") == '{"sentinel":true}\n'
