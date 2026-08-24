"""AS-CODER-ALPHA-WORKFLOW-METRICS-001 — objective North Star metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.workflow_metrics import (
    METRIC_IDS,
    PACKAGE_ID,
    WorkflowMetricsError,
    compile_workflow_metrics,
    write_workflow_metrics_receipt,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_empty_vault_does_not_fabricate_zeros(tmp_path: Path) -> None:
    report = compile_workflow_metrics(tmp_path)
    assert set(report["metrics"]) == set(METRIC_IDS)
    assert report["honesty"]["unknown_ne_zero"] is True
    assert report["honesty"]["not_instrumented_ne_zero"] is True
    assert report["honesty"]["telemetry_ne_truth_core"] is True
    assert report["privacy"]["raw_prompt_capture"] is False
    assert report["privacy"]["chat_transcript_capture"] is False
    for metric_id, item in report["metrics"].items():
        assert item["status"] in {"UNKNOWN", "NOT_INSTRUMENTED"}
        assert item["value"] is None
        assert item["value"] != 0
        assert metric_id == item["id"]
    assert report["metrics"]["TIME_TO_USEFUL_CONTEXT"]["status"] == "NOT_INSTRUMENTED"
    assert report["metrics"]["USER_CORRECTIONS_REQUIRED"]["status"] == "NOT_INSTRUMENTED"
    assert report["metrics"]["MISTAKES_PREVENTED"]["status"] == "NOT_INSTRUMENTED"
    assert report["metrics"]["HANDOFF_SUCCESS_RATE"]["status"] == "UNKNOWN"
    assert report["metrics"]["STALE_CONTEXT_RATE"]["status"] == "UNKNOWN"
    assert report["metrics"]["UNKNOWN_HONESTY"]["status"] == "UNKNOWN"
    assert report["metrics"]["MEANINGFUL_CHANGES_CAPTURED"]["status"] == "UNKNOWN"
    assert report["metrics"]["REEXPLANATION_RATE"]["status"] == "UNKNOWN"


def test_connect_receipt_without_clock_stays_not_instrumented(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "connect-receipt.json",
        {
            "schema": "atlas.connect.receipt.v1",
            "status": "connected",
            "generated": {"by": "atlas-coder-alpha-connect-001"},
        },
    )
    report = compile_workflow_metrics(tmp_path)
    metric = report["metrics"]["TIME_TO_USEFUL_CONTEXT"]
    assert metric["status"] == "NOT_INSTRUMENTED"
    assert metric["value"] is None
    assert "NFR-001" in metric["note"]


def test_handoff_creates_alone_do_not_imply_success_rate(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "handoffs" / "handoff-aaa.json",
        {"handoff_id": "handoff-aaa", "project_id": "harbor-api", "status": "created"},
    )
    _write(
        tmp_path / "generated" / "ops" / "handoffs" / "latest.json",
        {"handoff_id": "handoff-aaa", "project_id": "harbor-api"},
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["HANDOFF_SUCCESS_RATE"]
    assert metric["status"] == "UNKNOWN"
    assert metric["value"] is None
    assert "handoff_create_count=1" in metric["note"]


def test_resume_receipts_measure_handoff_success_rate(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "handoffs" / "handoff-aaa.json",
        {"handoff_id": "handoff-aaa", "project_id": "harbor-api"},
    )
    _write(
        tmp_path / "generated" / "ops" / "handoffs" / "resume-1.json",
        {"status": "resumed", "project_id": "harbor-api"},
    )
    _write(
        tmp_path / "generated" / "ops" / "handoffs" / "resume-2.json",
        {"status": "failed", "project_id": "harbor-api"},
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["HANDOFF_SUCCESS_RATE"]
    assert metric["status"] == "MEASURED"
    assert metric["value"] == 0.5


def test_session_captures_measure_meaningful_changes(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "session-captures" / "capture-1.json",
        {
            "capture_id": "capture-1",
            "project_id": "harbor-api",
            "changes": ["Added ADR-001"],
        },
    )
    _write(
        tmp_path / "generated" / "ops" / "session-captures" / "capture-2.json",
        {
            "capture_id": "capture-2",
            "project_id": "harbor-api",
            "changes": [],
        },
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["MEANINGFUL_CHANGES_CAPTURED"]
    assert metric["status"] == "MEASURED"
    assert metric["value"] == 1


def test_fresh_agent_receipts_measure_honesty_and_reexplanation(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "fresh-agent" / "harbor-api.json",
        {
            "project_id": "harbor-api",
            "metrics": {"UNKNOWN_HONESTY": 1.0, "STALE_CONTEXT_RATE": 0.0},
            "reexplanation_required": False,
        },
    )
    _write(
        tmp_path / "generated" / "ops" / "fresh-agent" / "harbor-ops.json",
        {
            "project_id": "harbor-ops",
            "metrics": {"UNKNOWN_HONESTY": 0.5},
            "reexplanation_required": True,
        },
    )
    report = compile_workflow_metrics(tmp_path)
    honesty = report["metrics"]["UNKNOWN_HONESTY"]
    reexplain = report["metrics"]["REEXPLANATION_RATE"]
    assert honesty["status"] == "MEASURED"
    assert honesty["value"] == 0.75
    assert reexplain["status"] == "MEASURED"
    assert reexplain["value"] == 0.5


def test_freshness_receipt_measures_stale_rate(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "context-freshness" / "harbor-api.json",
        {
            "project_id": "harbor-api",
            "metrics": {"STALE_CONTEXT_RATE": 0.25},
        },
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["STALE_CONTEXT_RATE"]
    assert metric["status"] == "MEASURED"
    assert metric["value"] == 0.25


def test_project_scope_does_not_import_sibling_receipts(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "fresh-agent" / "harbor-portal.json",
        {
            "project_id": "harbor-portal",
            "metrics": {"UNKNOWN_HONESTY": 0.0},
            "reexplanation_required": True,
        },
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    assert report["metrics"]["UNKNOWN_HONESTY"]["status"] == "UNKNOWN"
    assert report["metrics"]["UNKNOWN_HONESTY"]["value"] is None
    assert report["metrics"]["REEXPLANATION_RATE"]["status"] == "UNKNOWN"


def test_malformed_foreign_capture_never_fabricates_measured_zero(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "ops" / "session-captures"
    _write(
        root / "capture-foreign-valid.json",
        {
            "capture_id": "capture-foreign-valid",
            "project_id": "project-a",
            "changes": ["foreign change"],
        },
    )
    _write(
        root / "capture-malformed-scope.json",
        {"capture_id": "capture-malformed-scope", "changes": ["missing project_id"]},
    )
    (root / "capture-unreadable.json").write_text("{not-json", encoding="utf-8")
    report = compile_workflow_metrics(tmp_path, project_id="project-b")
    metric = report["metrics"]["MEANINGFUL_CHANGES_CAPTURED"]
    assert metric["status"] == "UNKNOWN"
    assert metric["value"] is None
    assert metric["value"] != 0.0


def test_reexplanation_requires_strict_json_boolean(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "ops" / "fresh-agent"
    matrix: list[tuple[str, object]] = [
        ("true-bool", True),
        ("false-bool", False),
        ("int-one", 1),
        ("int-zero", 0),
        ("float-one", 1.0),
        ("float-zero", 0.0),
        ("str-true", "true"),
        ("str-false", "false"),
        ("null", None),
        ("str-random", "maybe"),
    ]
    for name, value in matrix:
        payload: dict[str, object] = {"project_id": "harbor-api"}
        if value is not None:
            payload["reexplanation_required"] = value
        _write(root / f"{name}.json", payload)
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["REEXPLANATION_RATE"]
    assert metric["status"] == "MEASURED"
    assert metric["value"] == 0.5


def test_bool_subclass_does_not_count_as_numeric_metric(tmp_path: Path) -> None:
    _write(
        tmp_path / "generated" / "ops" / "fresh-agent" / "harbor-api.json",
        {
            "project_id": "harbor-api",
            "metrics": {"UNKNOWN_HONESTY": True},
        },
    )
    report = compile_workflow_metrics(tmp_path, project_id="harbor-api")
    metric = report["metrics"]["UNKNOWN_HONESTY"]
    assert metric["status"] == "UNKNOWN"
    assert metric["value"] is None


def test_receipt_write_is_deterministic(tmp_path: Path) -> None:
    first = write_workflow_metrics_receipt(tmp_path)
    second = write_workflow_metrics_receipt(tmp_path)
    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["package_id"] == PACKAGE_ID
    assert "generated_at" not in payload


def test_unmeasured_metric_cannot_carry_a_value() -> None:
    from project_atlas.workflow_metrics import _metric

    with pytest.raises(WorkflowMetricsError, match="unmeasured-metric"):
        _metric("STALE_CONTEXT_RATE", status="UNKNOWN", value=0.0, evidence=[], note="no")
