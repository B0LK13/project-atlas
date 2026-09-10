"""AS-STUDIO-A2-005 — intent continuity / interrupted session.

STALE_INTENT != PERMISSION
DUPLICATE_SUBMIT_RISK != AUTO_RETRY
INSPECT != EXECUTE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import cli as studio_cli  # noqa: E402
from atlas_studio import intent_continuity as ic  # noqa: E402

FIXED_NOW = "2026-09-09T12:00:00Z"


def clock():
    return FIXED_NOW


def _intent(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
        "intent_id": "intent-ownership-claim-abc",
        "action_type": "OWNERSHIP_CLAIM",
        "requested_at_utc": "2026-09-09T11:59:00Z",
        "max_age_seconds": 300,
        "agent": "agent-alpha",
        "lane": "pr/788",
    }
    base.update(overrides)
    return base


def _decision(**overrides):
    base = {
        "schema": "ATLAS_STUDIO_ACTION_DECISION_V1",
        "decision": "EXECUTED",
        "action_type": "OWNERSHIP_CLAIM",
        "intent_id": "intent-ownership-claim-abc",
        "mutated": True,
        "reasons": [],
        "evidence": {"mutation_state": "CONFIRMED"},
        "honesty": {},
        "evaluated_at_utc": FIXED_NOW,
    }
    base.update(overrides)
    return base


def test_fresh_intent():
    packet = ic.build_intent_continuity(intent=_intent(), clock=clock)
    assert packet["continuity_state"] == ic.FRESH
    assert packet["recovery"]["auto_retry"] is False
    assert ic.validate_intent_continuity(packet) == []


def test_stale_intent():
    packet = ic.build_intent_continuity(
        intent=_intent(requested_at_utc="2026-09-09T10:00:00Z", max_age_seconds=60),
        clock=clock,
    )
    assert packet["continuity_state"] == ic.STALE_INTENT


def test_already_decided_and_uncertain():
    done = ic.build_intent_continuity(
        intent=_intent(), decision=_decision(), clock=clock
    )
    assert done["continuity_state"] == ic.ALREADY_DECIDED

    uncertain = ic.build_intent_continuity(
        intent=_intent(),
        decision=_decision(
            decision="EXECUTION_FAILED",
            mutated=False,
            evidence={"mutation_state": "UNKNOWN"},
        ),
        clock=clock,
    )
    assert uncertain["continuity_state"] == ic.INTERRUPTED_UNCERTAIN
    ids = {a["id"] for a in uncertain["recovery"]["actions"]}
    assert "do_not_auto_retry" in ids


def test_duplicate_pending_execute():
    packet = ic.build_intent_continuity(
        intent=_intent(),
        decision=_decision(decision="EXECUTE_ALLOWED", mutated=False),
        clock=clock,
    )
    assert packet["continuity_state"] == ic.DUPLICATE_SUBMIT_RISK


def test_missing_intent_file(tmp_path: Path):
    packet = ic.build_intent_continuity(
        intent_file=tmp_path / "missing.json", clock=clock
    )
    assert packet["continuity_state"] == ic.MISSING


def test_cli_continuity_json(tmp_path: Path, capsys):
    from atlas_studio.snapshot import utcnow

    now = utcnow()
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(
        json.dumps(_intent(requested_at_utc=now, max_age_seconds=3600)),
        encoding="utf-8",
    )
    rc = studio_cli.main(
        ["intent-continuity", "--intent-file", str(intent_path), "--json"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["continuity_state"] == ic.FRESH
    assert out["recovery"]["auto_retry"] is False


def test_doctor_includes_a2_005(capsys):
    rc = studio_cli.main(["doctor", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    names = {c["name"] for c in report["checks"]}
    assert "a2_005_intent_continuity_schema" in names
    assert report["ok"] is True
