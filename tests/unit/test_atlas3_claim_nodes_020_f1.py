"""AT3-020-F1 — claim-nodes consume path must not treat a present non-file as absent.

`compile_claim_nodes` used `if not path.is_file()` then UNKNOWN. A directory
named declared.json reported NO_DECLARED_CLAIM_NODES. A symlink to a regular
file was followed and composed as a healthy harbor-api projection, including
a foreign decision node (DEC-LEAK).

Missing still stays missing. An existing symlink, directory, or unreadable
path fails closed as CLAIM_NODES_CORRUPT.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.claim_nodes import compile_claim_nodes
from project_atlas.atlas3.contracts import Atlas3Error


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _declared_dir(vault: Path) -> Path:
    path = vault / "generated" / "ops" / "atlas3" / "claim-nodes" / "harbor-api"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_claim_nodes(_vault(tmp_path), "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["reason"] == "NO_DECLARED_CLAIM_NODES"
    assert report["counts"]["nodes"] == 0
    assert report["model_is_owner"] is False


def test_directory_named_declared_json_fails_closed_not_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (_declared_dir(vault) / "declared.json").mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_claim_nodes(vault, "harbor-api")
    assert exc.value.code == "CLAIM_NODES_CORRUPT"


def test_symlink_declared_json_fails_closed_not_composed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    target = tmp_path / "foreign-declared.json"
    target.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "node_kind": "decision",
                        "node_id": "DEC-LEAK",
                        "label": "foreign owner decision",
                        "evidence_refs": ["doc:other#1"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (_declared_dir(vault) / "declared.json").symlink_to(target)
    with pytest.raises(Atlas3Error) as exc:
        compile_claim_nodes(vault, "harbor-api")
    assert exc.value.code == "CLAIM_NODES_CORRUPT"


def test_regular_declared_file_still_derives(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = _declared_dir(vault) / "declared.json"
    path.write_text(
        json.dumps(
            {
                "project_id": "harbor-api",
                "nodes": [
                    {
                        "node_kind": "requirement",
                        "node_id": "REQ-1",
                        "label": "local first",
                        "evidence_refs": ["doc:charter#1"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = compile_claim_nodes(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"]["requirement"] == 1
    assert report["nodes"][0]["node_id"] == "REQ-1"
    assert report["model_is_owner"] is False
