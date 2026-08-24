"""AS-ORCH-INTEGRATION-IV-001A — independent IV for AS-ORCH-001A validate-result.

Exercises the real CLI chain (subprocess → project_atlas.cli) against untrusted
AgentResultEnvelope JSON. Classification != execution; IV != merge authorization.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration import PACKAGE_ID

pytestmark = pytest.mark.integration

_NON_DISPATCH_TRANSITIONS = frozenset(
    {
        "OWNER_REQUIRED",
        "BLOCKED",
        "REJECTED",
        "BLOCKED_UNKNOWN_STATE",
        "REMEDIATION_REQUIRED",
        "RECERTIFY_REQUIRED",
    }
)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": "local", "agent_id": "iv-linux-001a"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {
            "receipt_id": "ASR-1234567890abcdef",
            "status": "valid",
            "event_id": "AE-orch-iv-001a",
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


def _run_validate_result(path: Path) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_atlas.cli",
            "orchestrator",
            "validate-result",
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
    assert report["merge_authorized"] is False
    assert report["package_id"] == PACKAGE_ID


def test_iv_001a_a_valid_pass_envelope_classified_without_authority(tmp_path: Path) -> None:
    path = tmp_path / "pass.json"
    _write_payload(path, _valid_payload())
    code, report = _run_validate_result(path)
    assert code == 0
    assert report["valid"] is True
    assert report["outcome"] == "PASS"
    assert report["workflow_state"] == "LOCAL_ACCEPTED"
    assert report["next_transition"] == "INTEGRATION_VERIFY"
    _assert_no_authority(report)


def test_iv_001a_b_merge_eligible_never_merge_never_execution(tmp_path: Path) -> None:
    path = tmp_path / "merge-eligible.json"
    _write_payload(
        path,
        _valid_payload(
            state="MERGE_ELIGIBLE",
            requested_transition="MERGE",
        ),
    )
    code, report = _run_validate_result(path)
    assert code == 0
    assert report["valid"] is True
    assert report["workflow_state"] == "OWNER_REQUIRED"
    assert report["next_transition"] == "OWNER_REQUIRED"
    assert report["next_transition"] != "MERGE"
    assert report["owner_required"] is True
    _assert_no_authority(report)


def test_iv_001a_c_tampered_and_invalid_fail_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    _write_payload(malformed, "{")
    code, report = _run_validate_result(malformed)
    assert code != 0
    assert report["valid"] is False
    assert report["next_transition"] == "REJECTED"
    _assert_no_authority(report)
    assert report["reasons"][0] == "malformed_or_schema_invalid"

    tampered = tmp_path / "tampered.json"
    _write_payload(tampered, _valid_payload(execution_authorized=True))
    code, report = _run_validate_result(tampered)
    assert code != 0
    assert report["valid"] is False
    assert report["next_transition"] == "REJECTED"
    _assert_no_authority(report)


def test_iv_001a_d_terminal_and_owner_gate_outcomes_stay_non_dispatch(tmp_path: Path) -> None:
    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "blocked",
            _valid_payload(
                outcome="BLOCKED",
                blockers=[{"code": "EXPLICIT_BLOCK", "detail": "iv"}],
            ),
            "BLOCKED",
        ),
        (
            "owner_gate",
            _valid_payload(state="MERGE_ELIGIBLE", requested_transition="MERGE"),
            "OWNER_REQUIRED",
        ),
        (
            "unknown_state",
            _valid_payload(
                state="CERTIFIED",
                outcome="PASS",
                producer={"role": "autonomous", "agent_id": "x"},
            ),
            "BLOCKED_UNKNOWN_STATE",
        ),
        (
            "target_moved",
            _valid_payload(observations={"target_moved": True, "unauthorized_mutations": 0}),
            "RECERTIFY_REQUIRED",
        ),
        (
            "integration_fail",
            _valid_payload(
                producer={"role": "integration", "agent_id": "iv-integration"},
                outcome="FAIL",
            ),
            "REMEDIATION_REQUIRED",
        ),
    ]
    for label, payload, expected_transition in cases:
        path = tmp_path / f"{label}.json"
        _write_payload(path, payload)
        code, report = _run_validate_result(path)
        assert code == 0, label
        assert report["valid"] is True, label
        assert report["next_transition"] == expected_transition, label
        assert report["next_transition"] in _NON_DISPATCH_TRANSITIONS, label
        _assert_no_authority(report)


def test_iv_001a_e_idempotent_revalidate_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "stable.json"
    _write_payload(path, _valid_payload())
    code1, first = _run_validate_result(path)
    code2, second = _run_validate_result(path)
    assert code1 == 0
    assert code2 == 0
    assert first == second
