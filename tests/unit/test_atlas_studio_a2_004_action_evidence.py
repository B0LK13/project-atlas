"""AS-STUDIO-A2-004 — action evidence + recovery.

EXECUTION_FAILURE != SUCCESS
UNCERTAIN_MUTATION != NOTHING_CHANGED
AUTO_RETRY = FORBIDDEN
CAPTURE != AUTHORITY
MONITOR_NE_REEXECUTE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import action_evidence as ae  # noqa: E402
from atlas_studio import cli as studio_cli  # noqa: E402

FIXED = "2026-09-09T16:00:00Z"


def clock():
    return FIXED


def _decision(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_DECISION_V1",
        "decision": "EXECUTED",
        "action_type": "OWNERSHIP_CLAIM",
        "intent_id": "intent-ownership-claim-deadbeef",
        "mutated": True,
        "reasons": [],
        "evidence": {"mutation_state": "CONFIRMED", "emit_status": "ok"},
        "honesty": {},
        "evaluated_at_utc": FIXED,
    }
    base.update(overrides)
    return base


def test_confirmed_success_schema():
    packet = ae.build_action_evidence(decision=_decision(), clock=clock)
    assert packet["outcome_class"] == ae.CONFIRMED_SUCCESS
    assert packet["recovery"]["auto_retry"] is False
    assert ae.validate_action_evidence(packet) == []
    assert packet["honesty"]["auto_retry_forbidden"] is True


def test_failed_uncertain_recovery_forbids_auto_retry():
    packet = ae.build_action_evidence(
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "UNKNOWN"},
            reasons=["executor raised"],
        ),
        clock=clock,
    )
    assert packet["outcome_class"] == ae.FAILED_UNCERTAIN
    assert packet["recovery"]["auto_retry"] is False
    ids = {a["id"] for a in packet["recovery"]["actions"]}
    assert "do_not_auto_retry" in ids
    assert "inspect_control_plane" in ids


def test_refused_and_pending_and_dry_run():
    refused = ae.build_action_evidence(
        decision=_decision(
            decision="REFUSED_ALREADY_OWNED",
            mutated=False,
            reasons=["lane owned"],
        ),
        clock=clock,
    )
    assert refused["outcome_class"] == ae.REFUSED

    pending = ae.build_action_evidence(
        decision=_decision(decision="EXECUTE_ALLOWED", mutated=False, dry_run=False),
        clock=clock,
    )
    assert pending["outcome_class"] == ae.PENDING_EXECUTE

    dry = ae.build_action_evidence(
        decision=_decision(decision="EXECUTE_ALLOWED", mutated=False, dry_run=True),
        clock=clock,
    )
    assert dry["outcome_class"] == ae.DRY_RUN


def test_unavailable_missing_file(tmp_path: Path):
    packet = ae.build_action_evidence(
        decision_file=tmp_path / "missing.json", clock=clock
    )
    assert packet["outcome_class"] == ae.UNAVAILABLE
    assert ae.validate_action_evidence(packet) == []


def test_spool_write_non_canonical(tmp_path: Path):
    spool = tmp_path / "spool"
    packet = ae.build_action_evidence(
        decision=_decision(),
        write_spool=True,
        spool_dir=spool,
        clock=clock,
    )
    assert packet["knowledge_spool"]["written"] is True
    assert packet["knowledge_spool"]["authority"] is False
    assert packet["knowledge_spool"]["canonical"] is False
    path = Path(packet["knowledge_spool"]["path"])
    assert path.is_file()
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["authority"] is False
    assert envelope["canonical"] is False


def test_spool_requires_dir():
    packet = ae.build_action_evidence(
        decision=_decision(), write_spool=True, spool_dir=None, clock=clock
    )
    assert packet["knowledge_spool"]["written"] is False
    assert packet["knowledge_spool"]["error"] == "SPOOL_DIR_REQUIRED"


def test_cli_action_evidence_json(tmp_path: Path, capsys):
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            _decision(
                decision="EXECUTION_FAILED",
                mutated=False,
                evidence={"mutation_state": "UNKNOWN"},
            )
        ),
        encoding="utf-8",
    )
    rc = studio_cli.main(
        ["action-evidence", "--decision-file", str(decision_path), "--json"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome_class"] == ae.FAILED_UNCERTAIN
    assert out["recovery"]["auto_retry"] is False


def test_doctor_includes_a2_004(capsys):
    rc = studio_cli.main(["doctor", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    names = {c["name"] for c in report["checks"]}
    assert "a2_004_action_evidence_schema" in names
    assert "a2_004_no_auto_retry" in names
    assert report["ok"] is True


def test_claim_execute_write_decision(tmp_path: Path, monkeypatch, capsys):
    """Durable decision path for action-evidence without granting mutation."""
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(
        json.dumps(
            {
                "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
                "intent_id": "intent-test-write",
                "action_type": "OWNERSHIP_CLAIM",
                "actor_agent_id": "agent-alpha",
                "requested_at_utc": FIXED,
                "max_age_seconds": 3600,
            }
        ),
        encoding="utf-8",
    )
    decision_out = tmp_path / "decision.json"
    canned = _decision(decision="REFUSED_POLICY", mutated=False)

    monkeypatch.setattr(
        studio_cli,
        "_load_intent_file",
        lambda p: json.loads(Path(p).read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        studio_cli,
        "_live_claim_context",
        lambda agent_id, repo=None: ({}, None, object()),
    )

    class _FakeGh:
        def __init__(self, repo=None):
            self.repo = repo

    monkeypatch.setitem(
        __import__("sys").modules,
        "atlas_dag.gh",
        type("M", (), {"GhClient": _FakeGh})(),
    )

    import atlas_studio.action_intent as gc

    monkeypatch.setattr(
        gc,
        "execute_ownership_claim",
        lambda *a, **k: canned,
    )

    rc = studio_cli.main(
        [
            "claim-execute",
            "--intent-file",
            str(intent_path),
            "--repo",
            "B0LK13/project-atlas",
            "--json",
            "--write-decision",
            str(decision_out),
        ]
    )
    assert rc == 1  # refused → non-zero
    assert decision_out.is_file()
    written = json.loads(decision_out.read_text(encoding="utf-8"))
    assert written["decision"] == "REFUSED_POLICY"
    evidence = ae.build_action_evidence(decision_file=decision_out, clock=clock)
    assert evidence["outcome_class"] == ae.REFUSED
    assert evidence["recovery"]["auto_retry"] is False
