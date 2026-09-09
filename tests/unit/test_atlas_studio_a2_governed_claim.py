"""AS-STUDIO-A2-001 — governed OWNERSHIP_CLAIM attack suite.

STUDIO_UI != AUTHORITY
REQUESTED != CLAIMED
PREVIEW != EXECUTION
STALE_INTENT != CURRENT_PERMISSION
CONTROL_PLANE_REVALIDATES_AT_EXECUTION
A1_TRUTH_BOUNDARY = PRESERVED
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import action_intent as gc  # noqa: E402
from atlas_studio import mission_control as mc  # noqa: E402
from test_atlas_dag_router import make_profile, write_registry  # noqa: E402

FIXED = "2026-09-09T12:00:00Z"
LATER = "2026-09-09T12:10:00Z"
REPO = "B0LK13/project-atlas"
AGENT = "ubuntu-main"
HEAD = "a" * 40
TREE = "b" * 40


def clock():
    return FIXED


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _claim_action(
    *,
    pr: int = 900,
    runnable: str = "RUNNABLE",
    eligible: bool = True,
    ownership: str = "UNOWNED",
    owner=None,
    blockers: list[str] | None = None,
    frozen: bool = False,
    head: str = HEAD,
) -> dict:
    lane = f"pr/{pr}"
    return {
        "action_id": f"{lane}:OWNERSHIP_CLAIM",
        "pr": pr,
        "lane": lane,
        "head": head,
        "tree": TREE,
        "action_type": "OWNERSHIP_CLAIM",
        "action_class": "WRITE",
        "runnable_state": runnable,
        "blocking_reasons": list(blockers or []),
        "agent_eligible": eligible,
        "ownership": ownership,
        "owner": owner,
        "frozen": frozen,
        "score_total": 99.0 if runnable == "RUNNABLE" else 1.0,
        "truth_fingerprint": _fp(f"claim-{pr}-{runnable}"),
    }


def _matrix(actions: list[dict], *, agent: str = AGENT) -> dict:
    return {
        "schema": "ATLAS_MULTIDIMENSIONAL_FRONTIER_V1",
        "generated_at_utc": FIXED,
        "agent": agent,
        "agent_status": "REGISTERED_ACTIVE",
        "frontier_fingerprint": _fp("frontier-" + agent),
        "actions": actions,
        "by_action_class": {},
        "typed_rankings": {},
    }


def _mc(fp: str | None = None, frontier_fp: str | None = None) -> dict:
    return {
        "schema": "ATLAS_STUDIO_MISSION_CONTROL_V1",
        "snapshot_fingerprint": fp or _fp("mc-live"),
        "provenance": {
            "frontier_fingerprint": frontier_fp or _fp("frontier-" + AGENT),
        },
    }


def _intent(
    *,
    registry_agent: str = AGENT,
    lane: str = "pr/900",
    mc_fp: str | None = None,
    frontier_fp: str | None = None,
    action_id: str | None = "pr/900:OWNERSHIP_CLAIM",
    head: str = HEAD,
    requested_at: str = FIXED,
    max_age: int = 120,
    caps: list[str] | None = None,
    target_agent: str | None = None,
) -> dict:
    return gc.build_ownership_claim_intent(
        agent_id=registry_agent,
        lane=lane,
        source_mc_fingerprint=mc_fp or _fp("mc-live"),
        source_frontier_fingerprint=frontier_fp or _fp("frontier-" + AGENT),
        candidate_action_id=action_id,
        target_head=head,
        target_agent_id=target_agent or registry_agent,
        capability_claims=caps or ["CLAIM_OWNERSHIP", "POST_EVENTS"],
        max_age_seconds=max_age,
        clock=lambda: requested_at,
    )


class FakeClient:
    def __init__(self, pr: int = 900, head: str = HEAD, tree: str = TREE):
        self.repo = REPO
        self._pr = pr
        self._head = head
        self._tree = tree
        self._posted: list[dict] = []
        self._events: list[dict] = []

    def open_prs(self):
        return [
            {
                "number": self._pr,
                "headRefOid": self._head,
                "headRefName": f"branch-{self._pr}",
                "baseRefName": "main",
            }
        ]

    def commit(self, sha):
        return {"sha": sha, "tree": self._tree}

    def default_branch(self):
        return "main"

    def branch_head(self, branch):
        return {"sha": "1" * 40, "tree": "2" * 40}

    def dag_issue(self):
        return {"number": 719}

    def issue_comments(self, number):
        return [
            {"body": "```json\n" + json.dumps(e, sort_keys=True) + "\n```"}
            for e in self._events
        ]

    def run_gh(self, args):
        self._posted.append(list(args))
        return ""

    def pr(self, number):
        return self.open_prs()[0]


# --- 1. stale intent --------------------------------------------------------


def test_stale_fingerprint_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    intent = _intent(mc_fp=_fp("old-mc"))
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(fp=_fp("new-mc")),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_STALE
    assert decision["mutated"] is False
    assert any("FINGERPRINT" in r for r in decision["reasons"])


def test_stale_max_age_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    intent = _intent(requested_at=FIXED, max_age=60)
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
        now_clock=lambda: LATER,
    )
    assert decision["decision"] == gc.REFUSED_STALE
    assert "INTENT_MAX_AGE_EXCEEDED" in decision["reasons"]


# --- 2. already owned by other ---------------------------------------------


def test_lane_owned_by_other_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    action = _claim_action(
        ownership="OWNED",
        owner="other-agent",
        runnable="BLOCKED",
        eligible=False,
        blockers=["OWNERSHIP_MUTEX_HELD_BY:other-agent"],
    )
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([action]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_ALREADY_OWNED
    assert decision["mutated"] is False


# --- 3. not runnable --------------------------------------------------------


def test_lane_not_runnable_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    action = _claim_action(
        runnable="BLOCKED",
        eligible=False,
        blockers=["STACK_RESTACK_REQUIRED"],
    )
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([action]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_NOT_RUNNABLE


# --- 4. lane substitution ---------------------------------------------------


def test_lane_substituted_after_intent_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    intent = _intent(lane="pr/900", action_id="pr/900:OWNERSHIP_CLAIM")
    # Attacker retargets lane/pr but keeps old candidate id.
    intent = dict(intent)
    intent["target_lane"] = "pr/901"
    intent["target_pr"] = 901
    live = _matrix(
        [
            _claim_action(pr=901),
            _claim_action(pr=900, runnable="BLOCKED", eligible=False),
        ]
    )
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=live,
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_TARGET_MISMATCH


# --- 5. agent substitution --------------------------------------------------


def test_agent_substituted_refused(tmp_path):
    registry = write_registry(
        tmp_path,
        [make_profile(), make_profile(agent_id="windows-main", platforms=["windows"])],
    )
    intent = _intent(registry_agent=AGENT)
    intent = dict(intent)
    intent["actor_agent_id"] = "windows-main"
    intent["target_agent_id"] = "windows-main"
    # Matrix still bound to original agent → mismatch.
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()], agent=AGENT),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] in (
        gc.REFUSED_AGENT_INVALID,
        gc.REFUSED_TARGET_MISMATCH,
    )


# --- 6. inactive / foreign agent --------------------------------------------


def test_inactive_agent_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile(active=False)])
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_AGENT_INVALID
    assert "AGENT_INACTIVE" in decision["reasons"]


def test_foreign_unregistered_agent_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    intent = _intent(registry_agent="ghost-agent")
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()], agent="ghost-agent"),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_AGENT_INVALID


# --- 7. missing capability --------------------------------------------------


def test_missing_capability_refused(tmp_path):
    registry = write_registry(
        tmp_path,
        [
            make_profile(
                capabilities=["READ_REPO", "READ_GITHUB"],
                event_permissions=[],
            )
        ],
    )
    decision = gc.evaluate_ownership_claim_intent(
        _intent(caps=["CLAIM_OWNERSHIP"]),
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_CAPABILITY


# --- 8. authorization-shaped fields rejected --------------------------------


def test_authz_fields_rejected_at_build_and_schema(tmp_path):
    with pytest.raises(gc.GovernedClaimError):
        gc.build_ownership_claim_intent(
            agent_id=AGENT,
            lane="pr/900",
            source_mc_fingerprint=_fp("mc"),
            extra_fields={"authorized": True},
            clock=clock,
        )
    intent = dict(_intent())
    intent["permitted"] = True
    errs = gc.validate_intent(intent)
    assert errs
    registry = write_registry(tmp_path, [make_profile()])
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_SCHEMA


def test_authz_grants_field_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    intent = dict(_intent())
    intent["grants"] = ["OWNERSHIP"]
    decision = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_SCHEMA


# --- 9. ranking alone does not authorize ------------------------------------


def test_ranking_without_eligibility_refused(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    # High score but not runnable / not eligible.
    action = _claim_action(
        runnable="BLOCKED",
        eligible=False,
        blockers=["NO_WRITE_CAPABILITY"],
    )
    action["score_total"] = 999.0
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([action]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_NOT_RUNNABLE


# --- 10. idempotent replay --------------------------------------------------


def test_replay_already_owned_idempotent_refusal(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    action = _claim_action(
        ownership="OWNED",
        owner=AGENT,
        runnable="NOT_APPLICABLE",
        eligible=False,
        blockers=["ALREADY_OWNED_BY_AGENT"],
    )
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([action]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert decision["decision"] == gc.REFUSED_IDEMPOTENT_ALREADY_CLAIMED
    assert decision["mutated"] is False


# --- 11. preview never emits ------------------------------------------------


def test_preview_never_calls_emit_event(monkeypatch, tmp_path):
    calls: list[object] = []

    def boom(*_a, **_k):
        calls.append(True)
        raise AssertionError("emit_event must not be called from preview")

    monkeypatch.setattr("atlas_dag.emitter.emit_event", boom)
    preview = gc.preview_ownership_claim(
        agent_id=AGENT,
        lane="pr/900",
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        clock=clock,
    )
    assert preview["schema"] == gc.SCHEMA_PREVIEW
    assert preview["honesty"]["preview_ne_execution"] is True
    assert calls == []
    assert gc.validate_preview(preview) == []


# --- 12. execute calls evaluate then emit only when allowed -----------------


def test_execute_path_evaluate_then_emit_when_allowed(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    intent = _intent()
    client = FakeClient()
    eval_calls = {"n": 0}
    emit_calls: list[dict] = []

    real_eval = gc.evaluate_ownership_claim_intent

    def wrapped_eval(*a, **k):
        eval_calls["n"] += 1
        return real_eval(*a, **k)

    def fake_emit(client_, registry_, payload, dry_run=False):
        emit_calls.append(payload)
        return "posted"

    monkeypatch.setattr(gc, "evaluate_ownership_claim_intent", wrapped_eval)

    # Refusal path: no emit.
    bad = dict(intent)
    bad["source_mc_fingerprint"] = _fp("stale")
    refused = gc.execute_ownership_claim(
        bad,
        client=client,
        registry=registry,
        frontier_matrix=matrix,
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=fake_emit,
    )
    assert refused["decision"] == gc.REFUSED_STALE
    assert emit_calls == []
    assert eval_calls["n"] >= 1

    # Allowed wet path: emit once.
    eval_calls["n"] = 0
    monkeypatch.setattr(
        "atlas_dag.emitter.resolve_context",
        lambda client, pr, profile, expected_repo=None: __import__(
            "atlas_dag.emitter", fromlist=["ResolvedContext"]
        ).ResolvedContext(
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
        ),
    )
    ok = gc.execute_ownership_claim(
        intent,
        client=client,
        registry=registry,
        frontier_matrix=matrix,
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=fake_emit,
        expected_repo=REPO,
    )
    assert ok["decision"] == gc.EXECUTED
    assert ok["mutated"] is True
    assert len(emit_calls) == 1
    assert emit_calls[0]["event"] == "OWNER_CLAIMED"
    assert eval_calls["n"] >= 1


# --- 13. A1 mc works without mutation imports -------------------------------


def test_a1_mc_without_action_intent_import():
    import importlib

    import atlas_studio.mission_control as mc_mod

    src = Path(mc_mod.__file__).read_text(encoding="utf-8")
    assert "action_intent" not in src
    # Fresh import path still builds.
    importlib.reload(mc_mod)
    from atlas_dag import control_view as cv_mod
    from atlas_dag import telemetry as tel_mod

    packet = mc_mod.build_mission_control(
        repository=REPO,
        control_view=cv_mod.build_global_control_view(
            repository=REPO,
            clock=clock,
            seal_scan="skipped_for_latency",
        ),
        telemetry_packet=tel_mod.build_coordination_telemetry(
            repository=REPO,
            clock=clock,
            seal_projection="deferred_or_skipped",
        ),
        clock=clock,
    )
    assert packet["schema"] == mc.SCHEMA_CONST
    assert mc_mod.validate_mission_control(packet) == []


# --- 14. positive eligible path ---------------------------------------------


def test_positive_eligible_dry_run_and_wet(monkeypatch, tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    intent = _intent()
    client = FakeClient()
    emit_calls: list[dict] = []

    def fake_emit(client_, registry_, payload, dry_run=False):
        emit_calls.append(payload)
        return "posted"

    monkeypatch.setattr(
        "atlas_dag.emitter.resolve_context",
        lambda client, pr, profile, expected_repo=None: __import__(
            "atlas_dag.emitter", fromlist=["ResolvedContext"]
        ).ResolvedContext(
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
        ),
    )

    allowed = gc.evaluate_ownership_claim_intent(
        intent,
        frontier_matrix=matrix,
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert allowed["decision"] == gc.EXECUTE_ALLOWED
    assert allowed["mutated"] is False

    dry = gc.execute_ownership_claim(
        intent,
        client=client,
        registry=registry,
        frontier_matrix=matrix,
        mission_control=_mc(),
        dry_run=True,
        clock=clock,
        emit_event=fake_emit,
    )
    assert dry["decision"] == gc.EXECUTE_ALLOWED  # DRY_RUN != EXECUTED
    assert dry["dry_run"] is True
    assert dry["mutated"] is False
    assert emit_calls == []

    wet = gc.execute_ownership_claim(
        intent,
        client=client,
        registry=registry,
        frontier_matrix=matrix,
        mission_control=_mc(),
        dry_run=False,
        clock=clock,
        emit_event=fake_emit,
        expected_repo=REPO,
    )
    assert wet["decision"] == gc.EXECUTED
    assert wet["mutated"] is True
    assert len(emit_calls) == 1


def test_list_claim_candidates_ro_projection():
    matrix = _matrix([_claim_action(), _claim_action(pr=901, runnable="BLOCKED", eligible=False)])
    listing = gc.list_claim_candidates(
        agent_id=AGENT,
        frontier_matrix=matrix,
        mission_control=_mc(),
        clock=clock,
    )
    assert len(listing["candidates"]) == 1
    assert listing["candidates"][0]["pr"] == 900
    assert listing["honesty"]["ranking_ne_authorization"] is True


def test_schemas_loadable_and_decision_validates(tmp_path):
    ok, detail = gc.schemas_loadable()
    assert ok, detail
    registry = write_registry(tmp_path, [make_profile()])
    decision = gc.evaluate_ownership_claim_intent(
        _intent(),
        frontier_matrix=_matrix([_claim_action()]),
        mission_control=_mc(),
        registry=registry,
        clock=clock,
    )
    assert gc.validate_decision(decision) == []
