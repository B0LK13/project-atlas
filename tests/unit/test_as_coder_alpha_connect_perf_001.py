"""AS-CODER-ALPHA-CONNECT-PERF-001 — baseline / regression-band honesty.

Live connect timings are observational. This module never asserts an SLA
or a wall-clock product threshold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.connect_perf import (
    DEPENDENCY_PR,
    PACKAGE_ID,
    ConnectPerfError,
    LaneSample,
    compare_cold_warm,
    report_as_dict,
    run_connect_perf_baseline,
    seed_perf_fixture,
)


def test_compare_cold_warm_is_not_an_sla() -> None:
    faster = compare_cold_warm(cold_ms=1000, warm_ms=80)
    assert faster["regression_band"] == "warm_faster"
    assert faster["sla_declared"] is False
    assert faster["warm_over_cold"] == 0.08
    slower = compare_cold_warm(cold_ms=100, warm_ms=140)
    assert slower["regression_band"] == "warm_slower"
    assert slower["sla_declared"] is False
    unknown = compare_cold_warm(cold_ms=0, warm_ms=10)
    assert unknown["regression_band"] == "unknown"
    assert unknown["warm_over_cold"] is None


def test_negative_duration_fail_closed() -> None:
    with pytest.raises(ConnectPerfError, match="negative"):
        compare_cold_warm(cold_ms=-1, warm_ms=1)


def test_receipt_schema_forbids_sla_and_authority_claims() -> None:
    samples = [
        LaneSample(
            name="cold_connect",
            wall_ms=12,
            files_inspected=2,
            files_reparsed=2,
            records_changed=2,
            writes=4,
            peak_rss_kb=None,
            notes="fixture",
        ),
        LaneSample(
            name="warm_unchanged_reconnect",
            wall_ms=3,
            files_inspected=2,
            files_reparsed=0,
            records_changed=0,
            writes=0,
            peak_rss_kb=None,
            notes="skip",
        ),
    ]
    payload = report_as_dict(
        samples,
        comparison=compare_cold_warm(cold_ms=12, warm_ms=3),
        project_id="perf-fixture",
    )
    assert payload["package"] == PACKAGE_ID
    assert payload["dependency_pr"] == DEPENDENCY_PR
    assert payload["merge_eligible_to_main"] is False
    assert payload["owner_merge_required"] is True
    assert payload["terminology"]["product_sla"] is False
    assert payload["performance_result"] == "OBSERVATIONAL"
    assert payload["honesty"]["baseline_ne_sla"] is True
    assert payload["honesty"]["incremental_skip_is_authority"] is False
    assert "generated_at" not in payload
    blob = json.dumps(payload)
    assert "COMMERCIAL_GA" not in blob
    assert "AUTHENTIC_PILOT=YES" not in blob


def test_live_cold_warm_and_lenses_are_measured(tmp_path: Path) -> None:
    project = seed_perf_fixture(tmp_path / "perf-root")
    report = run_connect_perf_baseline(project)
    names = [row["name"] for row in report["lanes"]]
    assert names == [
        "cold_connect",
        "warm_unchanged_reconnect",
        "one_file_delta",
        "brief_generation",
        "context_generation",
        "handoff_generation",
        "source_health",
        "atlas_next",
    ]
    by_name = {row["name"]: row for row in report["lanes"]}
    assert by_name["cold_connect"]["notes"] == "disposition=full_compile"
    assert isinstance(by_name["cold_connect"]["wall_ms"], int)
    assert by_name["cold_connect"]["wall_ms"] >= 0
    assert by_name["warm_unchanged_reconnect"]["notes"] == "disposition=no_change_skip"
    assert isinstance(by_name["warm_unchanged_reconnect"]["wall_ms"], int)
    assert by_name["warm_unchanged_reconnect"]["wall_ms"] >= 0
    assert by_name["warm_unchanged_reconnect"]["files_reparsed"] == 0
    assert by_name["warm_unchanged_reconnect"]["records_changed"] == 0
    assert by_name["one_file_delta"]["notes"] != "disposition=no_change_skip"
    assert by_name["one_file_delta"]["records_changed"] is not None
    assert by_name["source_health"]["writes"] == 0
    assert by_name["atlas_next"]["writes"] == 0
    assert report["cold_vs_warm"]["sla_declared"] is False
    assert report["performance_result"] == "OBSERVATIONAL"
    receipt = Path(report["receipt_path"])
    assert receipt.is_file()
    assert "generated/ops/connect-perf-baseline.json" in receipt.as_posix()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["honesty"]["perf_ne_product_gate"] is True
    assert (Path(report["vault"]) / "projects").is_dir()
    vault_blob = json.dumps(payload)
    assert "AKIA" not in vault_blob
    assert report["project_id"]
    assert report["project_id"] != "portal-app"
