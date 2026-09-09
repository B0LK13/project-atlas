"""AS-STUDIO-A2-001 review-closure hardening (PR #776 findings).

REPO_IDENTITY_AT_EXECUTE = EXPLICIT_OR_REFUSED
DUPLICATE_REGISTRATION = FAIL_CLOSED
EXECUTOR_FAILURE != SUCCESS
DRY_RUN != EXECUTED
A1_TRUTH_BOUNDARY = PRESERVED
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import action_intent as gc  # noqa: E402
from atlas_studio import cli as studio_cli  # noqa: E402
from atlas_studio import governance as gov  # noqa: E402
from test_atlas_dag_router import make_profile, write_registry  # noqa: E402
from test_atlas_studio_a2_governed_claim import (  # noqa: E402
    AGENT,
    HEAD,
    REPO,
    TREE,
    FakeClient,
    _claim_action,
    _intent,
    _matrix,
    _mc,
    clock,
)


@pytest.fixture
def registry_snapshot():
    """Registry is module-global; every test restores it exactly."""
    saved = dict(gov._REGISTRY)
    yield
    gov._REGISTRY.clear()
    gov._REGISTRY.update(saved)


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


class _Handler:
    action_type = "SYNTHETIC_ACTION"

    def __init__(self, apply=None):
        self._apply = apply

    def evaluate(self, intent, **kwargs):
        return gov.build_decision(
            gov.EXECUTE_ALLOWED,
            action_type=self.action_type,
            intent_id=intent.get("intent_id"),
            reasons=["SYNTHETIC_OK"],
        )

    def apply_authorized(self, intent, decision, **kwargs):
        if self._apply is None:
            return gov.build_decision(
                gov.EXECUTED,
                action_type=self.action_type,
                intent_id=intent.get("intent_id"),
                reasons=["SYNTHETIC_EXECUTED"],
                mutated=True,
            )
        return self._apply(intent, decision, **kwargs)


def _synthetic_intent() -> dict:
    return {"action_type": "SYNTHETIC_ACTION", "intent_id": "syn-1"}


# --- Finding: --repo omitted skips repo pinning -----------------------------


def test_wet_execute_without_expected_repo_refuses_before_resolve(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    emit_calls: list[dict] = []
    resolve_calls: list[int] = []

    def fake_resolve(*a, **k):
        resolve_calls.append(1)
        return _resolved_ctx(*a, **k)

    monkeypatch.setattr("atlas_dag.emitter.resolve_context", fake_resolve)
    decision = gc.execute_ownership_claim(
        _intent(),
        client=FakeClient(),
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=lambda *a, **k: emit_calls.append(a) or "posted",
        # expected_repo deliberately omitted
    )
    assert decision["decision"] == gc.REFUSED_POLICY
    assert "EXPECTED_REPO_REQUIRED_AT_EXECUTE" in decision["reasons"]
    assert decision["mutated"] is False
    assert emit_calls == []
    assert resolve_calls == []  # refused before any live resolution
    assert gc.validate_decision(decision) == []


def test_wet_execute_with_wrong_expected_repo_refuses(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    emit_calls: list[dict] = []
    decision = gc.execute_ownership_claim(
        _intent(),
        client=FakeClient(),  # client.repo == REPO
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=lambda *a, **k: emit_calls.append(a) or "posted",
        expected_repo="someone-else/other-repo",
    )
    assert decision["decision"] == gc.REFUSED_POLICY
    assert any("WRONG_REPOSITORY_IDENTITY" in r for r in decision["reasons"])
    assert decision["mutated"] is False
    assert emit_calls == []


def test_dry_run_does_not_require_expected_repo(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    decision = gc.execute_ownership_claim(
        _intent(),
        client=FakeClient(),
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        dry_run=True,
        clock=clock,
    )
    assert decision["decision"] == gc.EXECUTE_ALLOWED
    assert decision["dry_run"] is True
    assert decision["mutated"] is False


def test_cli_claim_execute_requires_repo(capsys):
    parser = studio_cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["claim-execute", "--intent-file", "x.json"])
    assert exc.value.code == 2
    assert "--repo" in capsys.readouterr().err


def test_cli_claim_execute_dry_run_exit_code_and_label(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    intent_path = tmp_path / "intent.json"
    # CLI has no clock injection: mint a wall-clock-fresh intent (max_age 120s).
    intent_path.write_text(json.dumps(_intent(requested_at=gc.utcnow())), encoding="utf-8")

    monkeypatch.setattr(
        studio_cli,
        "_live_claim_context",
        lambda agent_id, *, repo, clock=None: (_mc(), matrix, registry),
    )
    monkeypatch.setattr("atlas_dag.gh.GhClient", lambda repo=None: FakeClient())
    monkeypatch.setattr("atlas_dag.emitter.resolve_context", _resolved_ctx)
    emit_calls: list[dict] = []
    monkeypatch.setattr(
        "atlas_dag.emitter.emit_event",
        lambda *a, **k: emit_calls.append(a) or "posted",
    )

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = studio_cli.main(
            [
                "claim-execute",
                "--intent-file",
                str(intent_path),
                "--repo",
                REPO,
                "--dry-run",
                "--json",
            ]
        )
    out = json.loads(buf.getvalue())
    assert rc == 0
    assert out["decision"] == gc.EXECUTE_ALLOWED
    assert out["dry_run"] is True
    assert out["mutated"] is False
    assert emit_calls == []


# --- Finding: no-op comprehension / agent binding ----------------------------


def test_list_claim_candidates_refuses_foreign_agent_matrix():
    matrix = _matrix([_claim_action()], agent="someone-else")
    listing = gc.list_claim_candidates(
        agent_id=AGENT,
        frontier_matrix=matrix,
        mission_control=_mc(),
        clock=clock,
    )
    assert listing["candidates"] == []
    assert "AGENT_MATRIX_MISMATCH" in listing["notes"]
    src = Path(gc.__file__).read_text(encoding="utf-8")
    assert "if True]" not in src


# --- Finding: duplicate registration silently overwrote --------------------


def test_duplicate_registration_refused(registry_snapshot):
    first = _Handler()
    gov.register_action(first, notes="first")
    with pytest.raises(gov.GovernanceError, match="DUPLICATE_REGISTRATION:SYNTHETIC_ACTION"):
        gov.register_action(_Handler(), notes="takeover")
    assert gov.get_handler("SYNTHETIC_ACTION").handler is first


def test_same_handler_reregistration_is_idempotent(registry_snapshot):
    h = _Handler()
    gov.register_action(h)
    gov.register_action(h)
    assert gov.get_handler("SYNTHETIC_ACTION").handler is h


def test_explicit_replace_is_allowed(registry_snapshot):
    gov.register_action(_Handler())
    second = _Handler()
    gov.register_action(second, replace=True)
    assert gov.get_handler("SYNTHETIC_ACTION").handler is second


def test_ownership_claim_handler_cannot_be_silently_taken_over(registry_snapshot):
    class Rogue:
        action_type = gc.ACTION_OWNERSHIP_CLAIM

        def evaluate(self, intent, **kwargs):
            return gov.build_decision(
                gov.EXECUTE_ALLOWED,
                action_type=self.action_type,
                intent_id=None,
                reasons=["ROGUE"],
            )

        def apply_authorized(self, intent, decision, **kwargs):
            return self.evaluate(intent)

    before = gov.get_handler(gc.ACTION_OWNERSHIP_CLAIM).handler
    with pytest.raises(gov.GovernanceError):
        gov.register_action(Rogue())
    assert gov.get_handler(gc.ACTION_OWNERSHIP_CLAIM).handler is before


def test_not_started_attach_point_can_be_promoted(registry_snapshot):
    class Future:
        action_type = "CI_DISPATCH"

        def evaluate(self, intent, **kwargs):
            return gov.build_decision(
                gov.REFUSED_POLICY,
                action_type=self.action_type,
                intent_id=None,
                reasons=["TEST_ONLY"],
            )

        def apply_authorized(self, intent, decision, **kwargs):
            return self.evaluate(intent)

    assert gov.get_handler("CI_DISPATCH").status == "NOT_STARTED"
    gov.register_action(Future(), notes="test promotion only")
    assert gov.get_handler("CI_DISPATCH").status == "IMPLEMENTED"
    # declare_not_started must not demote an IMPLEMENTED entry.
    gov.declare_not_started("CI_DISPATCH")
    assert gov.get_handler("CI_DISPATCH").status == "IMPLEMENTED"


def test_future_intents_still_closed_after_snapshot_restore():
    """Guard the fixture itself: registry state leaks would hide closure."""
    for name in (
        "CI_DISPATCH",
        "IV_REQUEST",
        "HANDOFF_DELIVER",
        "STEAL_EXECUTE",
        "MERGE",
        "WORKTREE_OPEN",
    ):
        assert gov.get_handler(name).status == "NOT_STARTED", name
    assert gov.get_handler(gc.ACTION_OWNERSHIP_CLAIM).status == "IMPLEMENTED"


# --- Finding: executor exceptions escaped the substrate ---------------------


def test_executor_exception_becomes_execution_failed(registry_snapshot):
    def boom(intent, decision, **kwargs):
        raise RuntimeError("gh: network unreachable")

    gov.register_action(_Handler(apply=boom))
    decision = gov.execute_governed_intent(_synthetic_intent(), dry_run=False)
    assert decision["decision"] == gov.EXECUTION_FAILED
    assert decision["mutated"] is False
    assert decision["dry_run"] is False
    assert "EXECUTOR_EXCEPTION:RuntimeError" in decision["reasons"]
    assert decision["evidence"]["mutation_state"] == "UNKNOWN"
    assert decision["evidence"]["exception_message"] == "gh: network unreachable"
    assert decision["evidence"]["evaluate_decision"] == gov.EXECUTE_ALLOWED
    assert gc.validate_decision(decision) == []


def test_executor_invalid_return_becomes_execution_failed(registry_snapshot):
    gov.register_action(_Handler(apply=lambda intent, decision, **k: "posted"))
    decision = gov.execute_governed_intent(_synthetic_intent(), dry_run=False)
    assert decision["decision"] == gov.EXECUTION_FAILED
    assert "EXECUTOR_RETURN_INVALID" in decision["reasons"]
    assert decision["evidence"]["returned_type"] == "str"
    assert decision["mutated"] is False


def test_executor_failure_never_raises_from_claim_wet_path(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    monkeypatch.setattr("atlas_dag.emitter.resolve_context", _resolved_ctx)

    def emit_raises(*a, **k):
        raise OSError("socket closed after POST")

    decision = gc.execute_ownership_claim(
        _intent(),
        client=FakeClient(),
        registry=registry,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=emit_raises,
        expected_repo=REPO,
    )
    assert decision["decision"] == gc.EXECUTION_FAILED
    assert decision["action_type"] == gc.ACTION_OWNERSHIP_CLAIM
    assert decision["mutated"] is False
    assert decision["evidence"]["mutation_state"] == "UNKNOWN"


# --- Finding: dry-run was labelled EXECUTED ---------------------------------


def test_dry_run_label_is_execute_allowed_not_executed(registry_snapshot):
    calls: list[int] = []
    gov.register_action(_Handler(apply=lambda *a, **k: calls.append(1)))
    decision = gov.execute_governed_intent(_synthetic_intent(), dry_run=True)
    assert decision["decision"] == gov.EXECUTE_ALLOWED
    assert decision["dry_run"] is True
    assert decision["mutated"] is False
    assert calls == []
    assert decision["honesty"]["dry_run_ne_executed"] is True
    assert decision["honesty"]["execution_failure_ne_success"] is True


def test_wet_success_is_the_only_path_to_executed(registry_snapshot):
    gov.register_action(_Handler())
    decision = gov.execute_governed_intent(_synthetic_intent(), dry_run=False)
    assert decision["decision"] == gov.EXECUTED
    assert decision["mutated"] is True


# --- A1 boundary unchanged by this hardening --------------------------------


def test_a1_mission_control_still_free_of_governance_imports():
    from atlas_studio import mission_control as mc

    src = Path(mc.__file__).read_text(encoding="utf-8")
    for token in ("governance", "action_intent", "emit_event", "execute_governed"):
        assert token not in src, token
