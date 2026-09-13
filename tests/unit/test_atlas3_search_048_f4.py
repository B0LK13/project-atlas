"""AT3-048-F4 — memory reconcile consume path fails closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import OPS_RELATIVE, Atlas3Error
from project_atlas.atlas3.memory.reconcile_load import (
    load_memory_reconcile,
    reconciliation_block,
    reconciliation_conflicts,
    reconciliation_items,
)
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_recon(vault: Path, payload: object) -> Path:
    path = vault / OPS_RELATIVE / "memory" / "harbor-api" / "reconcile.json"
    path.parent.mkdir(parents=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_list_reconciliation_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(vault, {"reconciliation": ["not-an-object"]})
    artifact = load_memory_reconcile(vault, "harbor-api")
    with pytest.raises(Atlas3Error) as exc:
        reconciliation_block(artifact)
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert (
        main(["memory", "search", "secret", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_ERROR
    )


def test_corrupt_json_is_not_empty_search(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(vault, "{not json")
    with pytest.raises(Atlas3Error) as exc:
        load_memory_reconcile(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert (
        main(["memory", "search", "secret", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_ERROR
    )


def test_array_json_is_not_empty_search(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(vault, [{"items": [{"project_id": "other-api", "text": "foreign secret"}]}])
    with pytest.raises(Atlas3Error) as exc:
        load_memory_reconcile(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert (
        main(["memory", "search", "secret", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_ERROR
    )


def test_mixed_items_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(
        vault,
        {
            "reconciliation": {
                "items": [
                    {"project_id": "harbor-api", "text": "ok"},
                    "corrupt-row",
                ]
            }
        },
    )
    artifact = load_memory_reconcile(vault, "harbor-api")
    block = reconciliation_block(artifact)
    with pytest.raises(Atlas3Error) as exc:
        reconciliation_items(block, project_id="harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"


def test_non_object_conflicts_fail_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(vault, {"reconciliation": {"conflicts": ["x"]}})
    artifact = load_memory_reconcile(vault, "harbor-api")
    block = reconciliation_block(artifact)
    with pytest.raises(Atlas3Error) as exc:
        reconciliation_conflicts(block)
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert (
        main(["memory", "conflicts", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_ERROR
    )


def test_unknown_project_is_not_empty_search(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        load_memory_reconcile(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"
    assert (
        main(["memory", "search", "secret", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_ERROR
    )


def test_missing_reconcile_stays_empty(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    assert load_memory_reconcile(vault, "harbor-api") is None
    assert (
        main(["memory", "search", "secret", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_OK
    )


def test_valid_nested_reconcile_searches(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_recon(
        vault,
        {
            "reconciliation": {
                "items": [
                    {
                        "project_id": "harbor-api",
                        "text": "harbor postgres 15",
                        "item_type": "claim_candidate",
                    }
                ]
            }
        },
    )
    assert (
        main(["memory", "search", "postgres", "--vault", str(vault), "--project", "harbor-api"])
        == EXIT_OK
    )
