"""AS-STUDIO-A2-006 — mission session continuity hardening.

Proves:
- Fingerprint stable across wall-clock for unchanged inputs
- Malformed / conflicting evidence not reported as success or pending-execute
- Explicit --repo fail-closed when artifacts lack repo fields
- Orphan tmp alone vs tmp+final
- Persistence-failed never recommends replay
- Cross-process resume without writes
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
LATER = "2026-09-09T21:00:00Z"
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


def test_input_content_hashes_snapshot_point_in_time():
    """Injected objects get canonical hashes; file loads get byte hashes."""
    packet = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=clock
    )
    hashes = packet["provenance"]["input_content_hashes"]
    assert "intent_canonical" in hashes or "intent" in hashes
    assert "decision_canonical" in hashes or "decision" in hashes


def test_corrupt_json_file_is_corrupt_input(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    intent_path.write_bytes(b'{"schema":"ATLAS_STUDIO_ACTION_INTENT_V1",')  # truncated
    packet = ms.build_mission_session(intent_file=intent_path, clock=clock)
    assert packet["session_state"] == ms.SESSION_CORRUPT_INPUT
    assert packet["recovery"]["auto_retry"] is False
    assert ms.exit_code_for_session(packet) == 1


def test_byte_hash_matches_file_bytes(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    raw_i = json.dumps(_intent()).encode()
    raw_d = json.dumps(_decision()).encode()
    intent_path.write_bytes(raw_i)
    decision_path.write_bytes(raw_d)
    packet = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    import hashlib

    hashes = packet["provenance"]["input_content_hashes"]
    assert hashes["intent"] == hashlib.sha256(raw_i).hexdigest()
    assert hashes["decision"] == hashlib.sha256(raw_d).hexdigest()


def test_exit_codes():
    ok = ms.build_mission_session(intent=_intent(), decision=_decision(), clock=clock)
    assert ms.exit_code_for_session(ok) == 0
    uncertain = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "UNKNOWN", "repo": REPO},
        ),
        clock=clock,
    )
    assert ms.exit_code_for_session(uncertain) == 1
    persist = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(),
        persistence_failed_after_mutation=True,
        clock=clock,
    )
    assert ms.exit_code_for_session(persist) == 3


def test_success_session_schema():
    packet = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=clock
    )
    assert packet["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    assert packet["recovery"]["auto_retry"] is False
    assert packet["binding"]["binding_ok"] is True
    assert packet["dependencies"]["task_context"]["state"] == "UNAVAILABLE"
    assert packet["dependencies"]["control_plane_observation"]["state"] == "UNAVAILABLE"
    assert ms.validate_mission_session(packet) == []


def test_fingerprint_stable_across_wall_clock():
    """Unchanged inputs → same fingerprint even when clock advances."""
    s1 = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=lambda: FIXED
    )
    s2 = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=lambda: LATER
    )
    assert s1["generated_at_utc"] != s2["generated_at_utc"]
    assert s1["provenance"]["session_fingerprint"] == s2["provenance"]["session_fingerprint"]


def test_fingerprint_changes_when_decision_changes():
    s1 = ms.build_mission_session(
        intent=_intent(), decision=_decision(), clock=clock
    )
    s2 = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(decision="REFUSED_POLICY", mutated=False),
        clock=clock,
    )
    assert s1["provenance"]["session_fingerprint"] != s2["provenance"]["session_fingerprint"]


def test_malformed_decision_not_pending_execute():
    packet = ms.build_mission_session(
        intent=_intent(),
        decision={"schema": "ATLAS_STUDIO_ACTION_DECISION_V1", "intent_id": "intent-ownership-claim-session"},
        clock=clock,
    )
    assert packet["session_state"] != ms.SESSION_PENDING_EXECUTE
    assert packet["session_state"] in {
        ms.SESSION_INCOMPLETE,
        ms.SESSION_EVIDENCE_UNAVAILABLE,
        ms.SESSION_DECISION_MISSING,
    }


def test_malformed_intent_blocks_confirmed_success():
    packet = ms.build_mission_session(
        intent=_intent(schema="NOT_AN_INTENT"),
        decision=_decision(),
        clock=clock,
    )
    assert packet["session_state"] != ms.SESSION_CONFIRMED_SUCCESS
    assert packet["session_state"] in {
        ms.SESSION_INCOMPLETE,
        ms.SESSION_MISMATCHED_BINDING,
        ms.SESSION_UNAVAILABLE,
    }


def test_explicit_repo_unverified_without_artifact_fields():
    """Real intents lack repository; --repo must fail closed unless artifacts carry repo."""
    intent = _intent()
    decision = _decision()
    decision["evidence"] = {"mutation_state": "CONFIRMED"}  # no repo
    packet = ms.build_mission_session(
        intent=intent,
        decision=decision,
        expected_repository="wrong/repository",
        clock=clock,
    )
    assert packet["binding"]["binding_ok"] is False
    assert packet["session_state"] == ms.SESSION_MISMATCHED_BINDING
    assert "REPO_UNVERIFIED_IN_ARTIFACTS" in packet["binding"]["notes"]


def test_conflicting_evidence_same_intent_id():
    decision = _decision()
    stale_evidence = {
        "schema": "ATLAS_STUDIO_ACTION_EVIDENCE_V1",
        "outcome_class": "CONFIRMED_SUCCESS",
        "decision": _decision(
            decision="EXECUTED",
            evaluated_at_utc="2026-09-01T00:00:00Z",
            evidence={"mutation_state": "CONFIRMED", "repo": REPO},
        ),
        "recovery": {"actions": [], "auto_retry": False},
        "honesty": {},
        "provenance": {},
        "generated_at_utc": FIXED,
    }
    # Decision file says refused; evidence claims older success — conflict
    refused = _decision(decision="REFUSED_POLICY", mutated=False, evaluated_at_utc=FIXED)
    packet = ms.build_mission_session(
        intent=_intent(),
        decision=refused,
        evidence=stale_evidence,
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_CONFLICTING_EVIDENCE
    assert packet["lifecycle"]["evidence"]["conflicting_with_decision_file"] is True


def test_dry_run_not_refused():
    packet = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(decision="EXECUTE_ALLOWED", mutated=False, dry_run=True),
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_DRY_RUN


def test_failed_confirmed_no_mutation_not_refused():
    packet = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "NONE", "repo": REPO},
        ),
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_FAILED_CONFIRMED_NO_MUTATION


def test_mismatched_intent_binding():
    packet = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(intent_id="intent-OTHER"),
        clock=clock,
    )
    assert packet["session_state"] == ms.SESSION_MISMATCHED_BINDING
    assert packet["binding"]["binding_ok"] is False


def test_uncertain_and_persistence_failed_no_replay():
    uncertain = ms.build_mission_session(
        intent=_intent(),
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "UNKNOWN", "repo": REPO},
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
    assert persist["recovery"]["auto_retry"] is False
    assert "replay claim-execute after PERSISTENCE_FAILED_SIGNAL" in persist["resume"]["do_not"]
    blob = json.dumps(persist["recovery"]).lower()
    assert "auto-retry claim-execute" not in blob or "do not" in blob
    assert "do not re-execute" in blob or "do not" in blob


def test_orphan_tmp_alone_and_with_final(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    tmp_path_file = decision_path.with_suffix(".json.tmp")
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")

    # Alone: interrupted
    tmp_path_file.write_text(json.dumps(_decision()), encoding="utf-8")
    alone = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    assert alone["session_state"] == ms.SESSION_INTERRUPTED_ATOMIC_WRITE
    assert alone["lifecycle"]["interrupted_atomic_write"] is True

    # With final: prefer final; not interrupted success path
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    both = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=clock
    )
    assert both["lifecycle"]["interrupted_atomic_write"] is False
    assert both["lifecycle"]["orphan_tmp_with_final"] is True
    assert both["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    ids = {a["id"] for a in both["recovery"]["actions"]}
    assert "tmp_coexists_with_final" in ids


def test_cross_process_resume_no_writes(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    s1 = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=lambda: FIXED
    )
    s2 = ms.build_mission_session(
        intent_file=intent_path, decision_file=decision_path, clock=lambda: LATER
    )
    assert s1["session_state"] == ms.SESSION_CONFIRMED_SUCCESS
    assert s2["provenance"]["session_fingerprint"] == s1["provenance"]["session_fingerprint"]
    assert s2["recovery"]["auto_retry"] is False
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert before == after  # no unintended writes


def test_cli_mission_session_json(tmp_path: Path, capsys):
    intent_path = tmp_path / "intent.json"
    decision_path = tmp_path / "decision.json"
    intent_path.write_text(json.dumps(_intent()), encoding="utf-8")
    decision_path.write_text(
        json.dumps(
            _decision(
                decision="EXECUTION_FAILED",
                mutated=False,
                evidence={"mutation_state": "UNKNOWN", "repo": REPO},
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
    assert rc == 1  # FAILED_UNCERTAIN → recovery exit
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


def test_continuity_mismatched_binding_state():
    packet = ic.build_intent_continuity(
        intent=_intent(),
        decision=_decision(intent_id="intent-FOREIGN"),
        clock=clock,
    )
    assert packet["continuity_state"] == ic.MISMATCHED_BINDING


def test_write_decision_persistence_failure_after_mutation(
    tmp_path: Path, monkeypatch, capsys
):
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(
        json.dumps(_intent(actor_agent_id="agent-alpha")), encoding="utf-8"
    )
    blocked = tmp_path / "notadir"
    blocked.write_text("x", encoding="utf-8")
    out = blocked / "decision.json"

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
