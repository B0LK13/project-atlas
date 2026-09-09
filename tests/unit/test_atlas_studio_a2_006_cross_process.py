"""Cross-process acceptance for AS-STUDIO-A2-006 mission-session.

FIXTURE_LABELS (explicit):
  success_aligned — matching intent+decision files
  uncertain_mutation — EXECUTION_FAILED + mutation_state UNKNOWN
  malformed_truncated — truncated JSON intent
  binding_mismatch — decision intent_id foreign
  conflicting_evidence — refused decision + stale success evidence
  snapshot_inconsistent — decision evaluated_at before intent request

PROCESS_INTERRUPTION_TEST != POWER_LOSS_DURABILITY
AUTO_RETRY = false
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
FIXED = "2026-09-09T19:30:00Z"
REPO = "B0LK13/project-atlas"


def _intent(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
        "intent_id": "intent-ownership-claim-session",
        "action_type": "OWNERSHIP_CLAIM",
        "requested_at_utc": "2026-09-09T19:29:00Z",
        "max_age_seconds": 3600,
        "actor_agent_id": "agent-alpha",
        "target_lane": "pr/788",
        "target_pr": 788,
    }
    base.update(overrides)
    return base


def _decision(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_DECISION_V1",
        "decision": "EXECUTED",
        "action_type": "OWNERSHIP_CLAIM",
        "intent_id": "intent-ownership-claim-session",
        "mutated": True,
        "reasons": [],
        "evidence": {"mutation_state": "CONFIRMED", "repo": REPO, "lane": "pr/788"},
        "honesty": {},
        "evaluated_at_utc": FIXED,
    }
    base.update(overrides)
    return base


def _run_mission_session(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "atlas_studio", "mission-session", *extra, "--json"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "label,setup,expect_state,expect_rc",
    [
        (
            "success_aligned",
            lambda d: (
                (d / "intent.json").write_text(json.dumps(_intent()), encoding="utf-8"),
                (d / "decision.json").write_text(json.dumps(_decision()), encoding="utf-8"),
                ["--intent-file", str(d / "intent.json"), "--decision-file", str(d / "decision.json")],
            )[2],
            "CONFIRMED_SUCCESS",
            0,
        ),
        (
            "uncertain_mutation",
            lambda d: (
                (d / "intent.json").write_text(json.dumps(_intent()), encoding="utf-8"),
                (d / "decision.json").write_text(
                    json.dumps(
                        _decision(
                            decision="EXECUTION_FAILED",
                            mutated=False,
                            evidence={"mutation_state": "UNKNOWN", "repo": REPO},
                        )
                    ),
                    encoding="utf-8",
                ),
                ["--intent-file", str(d / "intent.json"), "--decision-file", str(d / "decision.json")],
            )[2],
            "FAILED_UNCERTAIN",
            1,
        ),
        (
            "malformed_truncated",
            lambda d: (
                (d / "intent.json").write_bytes(b'{"schema":"ATLAS_STUDIO_ACTION_INTENT_V1",'),
                ["--intent-file", str(d / "intent.json")],
            )[1],
            "CORRUPT_INPUT",
            1,
        ),
        (
            "binding_mismatch",
            lambda d: (
                (d / "intent.json").write_text(json.dumps(_intent()), encoding="utf-8"),
                (d / "decision.json").write_text(
                    json.dumps(_decision(intent_id="intent-FOREIGN")),
                    encoding="utf-8",
                ),
                ["--intent-file", str(d / "intent.json"), "--decision-file", str(d / "decision.json")],
            )[2],
            "MISMATCHED_BINDING",
            1,
        ),
        (
            "snapshot_inconsistent",
            lambda d: (
                (d / "intent.json").write_text(
                    json.dumps(_intent(requested_at_utc="2026-09-09T20:00:00Z")),
                    encoding="utf-8",
                ),
                (d / "decision.json").write_text(
                    json.dumps(_decision(evaluated_at_utc="2026-09-09T19:00:00Z")),
                    encoding="utf-8",
                ),
                ["--intent-file", str(d / "intent.json"), "--decision-file", str(d / "decision.json")],
            )[2],
            "SNAPSHOT_INCONSISTENT",
            1,
        ),
    ],
)
def test_cross_process_cli_states(tmp_path: Path, label, setup, expect_state, expect_rc):
    args = setup(tmp_path)
    proc = _run_mission_session(tmp_path, *args)
    assert proc.returncode == expect_rc, (label, proc.stderr, proc.stdout)
    packet = json.loads(proc.stdout)
    assert packet["session_state"] == expect_state, label
    assert packet["recovery"]["auto_retry"] is False
    assert "fixture_label" not in packet  # labels live in test ids only


def test_cross_process_fingerprint_stable(tmp_path: Path):
    intent = tmp_path / "intent.json"
    decision = tmp_path / "decision.json"
    intent.write_text(json.dumps(_intent()), encoding="utf-8")
    decision.write_text(json.dumps(_decision()), encoding="utf-8")
    args = ["--intent-file", str(intent), "--decision-file", str(decision)]
    p1 = _run_mission_session(tmp_path, *args)
    p2 = _run_mission_session(tmp_path, *args)
    assert p1.returncode == 0 and p2.returncode == 0
    a, b = json.loads(p1.stdout), json.loads(p2.stdout)
    assert a["provenance"]["session_fingerprint"] == b["provenance"]["session_fingerprint"]
    assert a["lifecycle"]["snapshot_consistency"]["status"] == "COHERENT"


def test_cross_process_conflicting_evidence(tmp_path: Path):
    intent = tmp_path / "intent.json"
    decision = tmp_path / "decision.json"
    evidence = tmp_path / "evidence.json"
    intent.write_text(json.dumps(_intent()), encoding="utf-8")
    refused = _decision(decision="REFUSED_POLICY", mutated=False)
    decision.write_text(json.dumps(refused), encoding="utf-8")
    evidence.write_text(
        json.dumps(
            {
                "schema": "ATLAS_STUDIO_ACTION_EVIDENCE_V1",
                "outcome_class": "CONFIRMED_SUCCESS",
                "decision": _decision(
                    evaluated_at_utc="2026-09-01T00:00:00Z",
                    evidence={"mutation_state": "CONFIRMED", "repo": REPO},
                ),
                "recovery": {"actions": [], "auto_retry": False},
                "honesty": {},
                "provenance": {},
                "generated_at_utc": FIXED,
            }
        ),
        encoding="utf-8",
    )
    proc = _run_mission_session(
        tmp_path,
        "--intent-file",
        str(intent),
        "--decision-file",
        str(decision),
        "--evidence-file",
        str(evidence),
    )
    assert proc.returncode == 1
    packet = json.loads(proc.stdout)
    assert packet["session_state"] == "CONFLICTING_EVIDENCE"
    assert packet["recovery"]["auto_retry"] is False
