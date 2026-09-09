"""AS-STUDIO-A2-006 — mission session continuity + cross-process resume.

SESSION != AUTHORITY
AUTO_RETRY = FORBIDDEN
MISMATCHED_BINDING != SUCCESS
PERSISTENCE_FAILED != CONFIRMED_SUCCESS
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import cli as studio_cli  # noqa: E402
from atlas_studio import intent_continuity as ic  # noqa: E402
from atlas_studio import mission_session as ms  # noqa: E402

FIXED = "2026-09-09T19:30:00Z"
REPO = "B0LK13/project-atlas"


def clock():
    return FIXED


def _intent(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
        "intent_id": "intent-ownership-claim-session",
        "action_type": "OWNERSHIP_CLAIM",
        "requested_at_utc": "2026-09-09T19:29:00Z",
        "max_age_seconds": 3600,
        "repository": REPO,
        "actor_agent_id": "agent-alpha",
        "lane": "pr/788",
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
        "evidence": {"mutation_state": "CONFIRMED", "repo": REPO},
        "honesty": {},
        "evaluated_at_utc": FIXED,
        "repository": REPO,
    }
    base.update(overrides)
    return base


def test_success_session_schema():
    packet = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=clock
    )
    assert packet["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    assert packet["recovery"]["auto_retry"] is False
    assert packet["binding"]["binding_ok"] is True
    assert packet["dependencies"]["task_context"]["state"] == "UNAVAILABLE"
    assert ms.validate_mission_session(packet) == []


def test_mismatched_intent_binding():
    packet = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(intent_id="intent-OTHER"),
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_MISMATCHED_BINDING
    assert packet["binding"]["binding_ok"] is False


def test_mismatched_repo_binding():
    packet = ms.build_mission_session(
        intent=_intent(repository="other/repo"),
        decision=_decision(),
        expected_repository=REPO,
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_MISMATCHED_BINDING


def test_uncertain_and_persistence_failed():
    uncertain = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "UNKNOWN"},
        ),
        clock=clock,
    )
    assert uncertain["session_state"] == ms.SESSION_FAILED_UNCERTAIN

    persist = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(),
        persistence_failed_after_mutation=True,
        clock=clock,
    )
    assert persist["session_state"] == ms.SESSION_PERSISTENCE_FAILED_SIGNAL
    ids = {a["id"] for a in persist["recovery"]["actions"]}
    assert "persistence_failed_after_possible_mutation" in ids


def test_continuity_mismatched_binding_state():
    packet = ic.build_intent_continuity(
        intent=_intent(),
        decision=_decision(intent_id="intent-FOREIGN"),
        clock=clock,
    )
    assert packet["continuity_state"] == ic.MISMATCHED_BINDING


def test_interrupted_atomic_write_orphan_tmp(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    tmp_path_file = decision_path.with_suffix(".json.tmp")
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")
    tmp_path_file.write_text(json.dumps(_decision()), encoding="utf-8")
    # Final decision.json absent → interrupted replace
    packet = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    assert packet["session_state"] == ms.SESSION_INTERRUPTED_ATOMIC_WRITE
    assert packet["lifecycle"]["interrupted_atomic_write"] is True
    ids = {a["id"] for a in packet["recovery"]["actions"]}
    assert "interrupted_atomic_write" in ids
    assert packet["recovery"]["auto_retry"] is False


def test_cross_process_resume(tmp_path: Path):
    """Fresh process loads persisted files and does not re-execute."""
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")

    # Session 1
    s1 = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    assert s1["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    fp1 = s1["provenance"]["session_fingerprint"]

    # Session 2 (simulated new process — rebuild from disk only)
    s2 = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    assert s2["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    assert s2["provenance"]["session_fingerprint"] == fp1
    assert "auto-retry claim-execute" in s2["resume"]["do_not"]
    assert s2["recovery"]["auto_retry"] is False


def test_cli_mission_session_json(tmp_path: Path, capsys):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")
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
        [
            "mission-session",
            "--intent-file",
            str(intent_path),
            "--decision-file",
            str(decision_path),
            "--json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["session_state"] == ms.SESSION_FAILED_UNCERTAIN
    assert out["recovery"]["auto_retry"] is False


def test_doctor_includes_a2_006(capsys):
    rc = studio_cli.main(["doctor", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    names = {c["name"] for c in report["checks"]}
    assert "a2_006_mission_session_schema" in names
    assert "a2_006_task_context_dependency_explicit" in names
    assert report["ok"] is True


def test_write_decision_persistence_failure_after_mutation(
    tmp_path: Path, monkeypatch, capsys
):
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(
        json.dumps(_intent(actor_agent_id="agent-alpha")), encoding="utf-8"
    )
    # Unwritable path: file that is a directory's child under a file-as-parent trick
    blocked = tmp_path / "notadir"
    blocked.write_text("x", encoding="utf-8")
    out = blocked / "decision.json"  # parent is a file → OSError

    canned = _decision(mutated=True, decision="EXECUTED")
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

    monkeypatch.setattr(gc, "execute_ownership_claim", lambda *a, **k: canned)

    rc = studio_cli.main(
        [
            "claim-execute",
            "--intent-file",
            str(intent_path),
            "--repo",
            REPO,
            "--json",
            "--write-decision",
            str(out),
        ]
    )
    assert rc == 3
    err = capsys.readouterr().err
    assert "PERSISTENCE_FAILED_AFTER_MUTATION" in err
