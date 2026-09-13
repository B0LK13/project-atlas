"""AT3-012-F1 — estate-nodes consume path must not treat a present non-file as absent.

`compile_estate_nodes` used `if not path.is_file()` then UNKNOWN. A directory
named declared.json reported NO_DECLARED_ESTATE_NODES. A symlink to a regular
file was followed (`Path.is_file()` follows links) and composed as a healthy
harbor-api projection, including services that never lived under that project.

Missing still stays missing. An existing symlink, directory, or unreadable
path fails closed as ESTATE_NODES_CORRUPT.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.estate_nodes import compile_estate_nodes


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _declared_dir(vault: Path) -> Path:
    path = vault / "generated" / "ops" / "atlas3" / "estate-nodes" / "harbor-api"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_missing_declared_stays_unknown(tmp_path: Path) -> None:
    report = compile_estate_nodes(_vault(tmp_path), "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["reason"] == "NO_DECLARED_ESTATE_NODES"
    assert report["counts"] == {"services": 0, "environments": 0}


def test_directory_named_declared_json_fails_closed_not_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    (_declared_dir(vault) / "declared.json").mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_estate_nodes(vault, "harbor-api")
    assert exc.value.code == "ESTATE_NODES_CORRUPT"


def test_symlink_declared_json_fails_closed_not_composed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    target = tmp_path / "foreign-declared.json"
    target.write_text(
        json.dumps(
            {
                "services": [
                    {"id": "leaked-db", "evidence_refs": ["doc:other#db"]},
                ],
                "environments": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (_declared_dir(vault) / "declared.json").symlink_to(target)
    with pytest.raises(Atlas3Error) as exc:
        compile_estate_nodes(vault, "harbor-api")
    assert exc.value.code == "ESTATE_NODES_CORRUPT"


def test_regular_declared_file_still_derives(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = _declared_dir(vault) / "declared.json"
    path.write_text(
        json.dumps(
            {
                "project_id": "harbor-api",
                "services": [{"id": "api", "evidence_refs": ["doc:compose.yml#api"]}],
                "environments": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = compile_estate_nodes(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"]["services"] == 1
    assert report["services"][0]["id"] == "api"
