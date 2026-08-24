"""AS-ORCH-INTEGRATION-IV-001B — independent IV for AS-ORCH-001B route-result.

CLI chain: subprocess → atlas orchestrator route-result. Routing != dispatch.
IV != merge authorization.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration import POLICY_ID, ROUTING_PACKAGE_ID

pytestmark = pytest.mark.integration


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": "local", "agent_id": "iv-linux-001b"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {
            "receipt_id": "ASR-1234567890abcdef",
            "status": "valid",
            "event_id": "AE-orch-iv-001b",
        },
        "blockers": [],
        "requested_transition": None,
    }
    payload.update(overrides)
    return payload


def _write_payload(path: Path, payload: dict[str, Any] | str) -> None:
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _run_route_result(path: Path) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_atlas.cli",
            "orchestrator",
            "route-result",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(proc.stdout)
    return proc.returncode, report


def _assert_no_authority(report: dict[str, Any]) -> None:
    assert report["execution_authorized"] is False
    assert report["permissions"]["merge"] is False
    assert report["permissions"]["authority_grant"] is False
    assert report["permissions"]["production_mutation"] is False
    assert report["policy_id"] == POLICY_ID
    assert report["package_id"] == ROUTING_PACKAGE_ID


def test_iv_001b_a_valid_pass_routes_task_without_authority(tmp_path: Path) -> None:
    path = tmp_path / "pass.json"
    _write_payload(path, _valid_payload())
    code, report = _run_route_result(path)
    assert code == 0
    assert report["transition"] == "INTEGRATION_VERIFY"
    assert report["route_kind"] == "task"
    assert report["task_type"] == "candidate_verification"
    # Policy may mark the route dispatchable; that is not execution authority.
    _assert_no_authority(report)


def test_iv_001b_b_merge_eligible_is_owner_gate_never_merge(tmp_path: Path) -> None:
    path = tmp_path / "merge-eligible.json"
    _write_payload(
        path,
        _valid_payload(state="MERGE_ELIGIBLE", requested_transition="MERGE"),
    )
    code, report = _run_route_result(path)
    assert code == 0
    assert report["route_kind"] == "owner_gate"
    assert report["transition"] == "OWNER_REQUIRED"
    assert report["transition"] != "MERGE"
    assert report["owner_gate"] is True
    assert report.get("task_type") in {None, ""}
    _assert_no_authority(report)


def test_iv_001b_c_malformed_and_tampered_fail_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    _write_payload(malformed, "{")
    code, report = _run_route_result(malformed)
    assert code != 0
    assert report["route_kind"] == "terminal"
    assert report["transition"] == "REJECTED"
    assert report["execution_authorized"] is False

    tampered = tmp_path / "tampered.json"
    _write_payload(tampered, _valid_payload(execution_authorized=True))
    code, report = _run_route_result(tampered)
    assert code != 0
    assert report["transition"] == "REJECTED"
    assert report["execution_authorized"] is False


def test_iv_001b_d_blocked_is_terminal_non_dispatch(tmp_path: Path) -> None:
    path = tmp_path / "blocked.json"
    _write_payload(
        path,
        _valid_payload(
            outcome="BLOCKED",
            blockers=[{"code": "EXPLICIT_BLOCK", "detail": "iv"}],
        ),
    )
    code, report = _run_route_result(path)
    assert code == 0
    assert report["route_kind"] == "terminal"
    assert report["transition"] == "BLOCKED"
    assert report.get("task_type") in {None, ""}
    _assert_no_authority(report)


def test_iv_001b_e_idempotent_reroute_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "stable.json"
    _write_payload(path, _valid_payload())
    code1, first = _run_route_result(path)
    code2, second = _run_route_result(path)
    assert code1 == 0
    assert code2 == 0
    assert first == second
