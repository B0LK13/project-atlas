"""AS-STUDIO-A2-001 — repository identity bound into the typed intent.

INTENT_REPO = PART_OF_INTENT_IDENTITY
INTENT_REPO != LIVE_REPO -> REFUSED_TARGET_MISMATCH
INTENT_REPO != EXPECTED_REPO -> REFUSED_TARGET_MISMATCH
UNBOUND_LEGACY_INTENT = STILL_REQUIRES_EXPLICIT_PIN
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import action_intent as gc  # noqa: E402
from atlas_studio import cli as studio_cli  # noqa: E402
from test_atlas_dag_router import make_profile, write_registry  # noqa: E402
from test_atlas_studio_a2_governed_claim import (  # noqa: E402
    AGENT,
    HEAD,
    REPO,
    TREE,
    FakeClient,
    _claim_action,
    _fp,
    _intent,
    _matrix,
    _mc,
    clock,
)


def _mc_with_repo(repo: str | None) -> dict:
    packet = _mc()
    if repo is not None:
        packet["repository"] = repo
    return packet


def _bound_intent(repo: str | None = REPO) -> dict:
    return gc.build_ownership_claim_intent(
        agent_id=AGENT,
        lane="pr/900",
        source_mc_fingerprint=_fp("mc-live"),
        source_frontier_fingerprint=_fp("frontier-" + AGENT),
        candidate_action_id="pr/900:OWNERSHIP_CLAIM",
        target_head=HEAD,
        target_repo=repo,
        clock=clock,
    )


def _resolved_ctx(client, pr, profile, expected_repo=None):
    from atlas_dag.emitter import ResolvedContext

    return ResolvedContext(
        repo=REPO,
        pr=pr,
        lane=f"pr/{pr}",
        head=HEAD,
        tree=TREE,
        base_branch="main",
        base_head="1" * 40,
        main_branch="main",
        main_head="1" * 40,
        parent_pr=None,
        parent_head=None,
        actor=AGENT,
        role="coordinator",
        session_id="sess-test",
    )


def test_target_repo_is_part_of_intent_identity():
    a = _bound_intent(REPO)
    b = _bound_intent("someone-else/other")
    c = _bound_intent(None)
    assert a["target_repo"] == REPO
    assert c["target_repo"] is None
    assert len({a["intent_id"], b["intent_id"], c["intent_id"]}) == 3
    assert gc.validate_intent(a) == []
    assert gc.validate_intent(c) == []


def test_unknown_and_whitespace_repo_are_unbound():
    assert gc.normalise_repo("UNKNOWN") is None
    assert gc.normalise_repo("  ") is None
    assert gc.normalise_repo(None) is None
    assert gc.normalise_repo(" owner/name ") == "owner/name"
    assert _bound_intent("UNKNOWN")["target_repo"] is None


def test_evaluate_refuses_intent_bound_to_another_repo(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    decision = gc.evaluate_ownership_claim_intent(
        _bound_intent(REPO),
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc_with_repo("someone-else/other"),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_TARGET_MISMATCH
    assert "INTENT_REPO_NE_LIVE_REPO" in decision["reasons"]
    assert decision["evidence"] == {
        "intent_repo": REPO,
        "live_repo": "someone-else/other",
    }
    assert gc.validate_decision(decision) == []


def test_evaluate_allows_matching_or_unobserved_live_repo(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    for live in (REPO, "UNKNOWN", None):
        decision = gc.evaluate_ownership_claim_intent(
            _bound_intent(REPO),
            frontier_matrix=_matrix([_claim_action()]),
            mission_control=_mc_with_repo(live),
            registry=registry,
            clock=clock,
        )
        assert decision["decision"] == gc.EXECUTE_ALLOWED, live


def test_legacy_unbound_intent_still_evaluates(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),  # helper mints without target_repo
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc_with_repo("someone-else/other"),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.EXECUTE_ALLOWED


def test_execute_refuses_pin_that_disagrees_with_intent(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    resolve_calls: list[int] = []
    emit_calls: list[dict] = []

    def fake_resolve(*a, **k):
        resolve_calls.append(1)
        return _resolved_ctx(*a, **k)

    monkeypatch.setattr("atlas_dag.emitter.resolve_context", fake_resolve)
    decision = gc.execute_ownership_claim(
        _bound_intent(REPO),
        client=FakeClient(),
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc_with_repo(REPO),
        dry_run=False,
        clock=clock,
        emit_event=lambda *a, **k: emit_calls.append(a) or "posted",
        expected_repo="someone-else/other",
    )
    assert decision["decision"] == gc.REFUSED_TARGET_MISMATCH
    assert "INTENT_REPO_NE_EXPECTED_REPO" in decision["reasons"]
    assert decision["mutated"] is False
    assert resolve_calls == []
    assert emit_calls == []


def test_execute_bound_intent_with_matching_pin_executes(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    emit_calls: list[dict] = []
    monkeypatch.setattr("atlas_dag.emitter.resolve_context", _resolved_ctx)
    decision = gc.execute_ownership_claim(
        _bound_intent(REPO),
        client=FakeClient(),
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc_with_repo(REPO),
        dry_run=False,
        clock=clock,
        emit_event=lambda *a, **k: emit_calls.append(a) or "posted",
        expected_repo=REPO,
    )
    assert decision["decision"] == gc.EXECUTED
    assert decision["mutated"] is True
    assert len(emit_calls) == 1


def test_cli_claim_intent_binds_observed_repository(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    monkeypatch.setattr(
        studio_cli,
        "_live_claim_context",
        lambda agent_id, *, repo, clock=None: (_mc_with_repo(REPO), matrix, registry),
    )
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = studio_cli.main(
            ["claim-intent", "--agent", AGENT, "--lane", "pr/900", "--repo", "cli/override"]
        )
    assert rc == 0
    intent = json.loads(buf.getvalue())
    # Observed MC repository wins over the CLI flag; the flag is only a fallback.
    assert intent["target_repo"] == REPO
    assert gc.validate_intent(intent) == []


def test_doctor_decision_vocabulary_check_passes():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = studio_cli.main(["doctor", "--json"])
    report = json.loads(buf.getvalue())
    checks = {c["name"]: c for c in report["checks"]}
    assert checks["a2_decision_vocabulary_matches_schema"]["ok"] is True, checks[
        "a2_decision_vocabulary_matches_schema"
    ]
    assert rc == 0
