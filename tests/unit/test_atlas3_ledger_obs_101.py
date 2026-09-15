"""AT3-101 — isolated ledger observability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.ledger import append_event
from project_atlas.atlas3.ledger_obs import PACKAGE_ID, compile_ledger_observability


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _ledger_path(vault: Path) -> Path:
    return vault / "generated" / "ops" / "atlas3" / "ledger" / "harbor-api.jsonl"


def test_empty_ledger_is_unknown_not_healthy(tmp_path: Path) -> None:
    report = compile_ledger_observability(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["integrity_state"] == "VALID"
    assert report["event_count"] == 0
    assert report["healthy"] is False
    assert report["ledger_is_truth_core"] is False
    assert report["filtered_corrupt_rows"] == 0
    assert report["new_cli_command"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["write_applied"] is False


def test_validated_rows_do_not_claim_truth_or_health(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    report = compile_ledger_observability(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["integrity_state"] == "VALID"
    assert report["event_count"] == 1
    assert report["healthy"] is False
    assert report["ledger_is_truth_core"] is False


def test_malformed_json_does_not_report_healthy_count(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    path = _ledger_path(vault)
    path.write_text(path.read_text(encoding="utf-8") + "{not-json\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_ledger_observability(vault, "harbor-api")
    assert exc.value.code == "LEDGER_CORRUPT"


def test_foreign_row_does_not_report_filtered_healthy(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    append_event(
        vault,
        "harbor-api",
        event_type="TEST_PASSED",
        source_plane="engineering",
        summary="ok",
    )
    path = _ledger_path(vault)
    foreign = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    foreign["project_id"] = "other-api"
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(foreign, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_ledger_observability(vault, "harbor-api")
    assert exc.value.code == "PROJECT_MISMATCH"


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/ledger_obs.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
        "add_parser",
        "ledger_status(",
    ):
        assert name not in source
