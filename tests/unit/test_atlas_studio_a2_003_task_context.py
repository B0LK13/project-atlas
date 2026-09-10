"""AS-STUDIO-A2-003 — Task Context + Continuation (read-only, one lane).

TASK_CONTEXT != AUTHORITY · NEXT_STEP != AUTHORIZATION · CONTINUATION != EXECUTION
KNOWN / UNKNOWN / STALE / CONFLICT / UNAVAILABLE stated, never guessed
MISSING_SHOWN_EXPLICITLY · A1_TRUTH_BOUNDARY = PRESERVED
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import cli as studio_cli  # noqa: E402
from atlas_studio import task_context as tc  # noqa: E402
from test_atlas_studio_a2_governed_claim import (  # noqa: E402
    AGENT,
    HEAD,
    REPO,
    TREE,
    _claim_action,
    _fp,
    _matrix,
    _mc,
    clock,
)

FIXED = "2026-09-09T12:00:00Z"


def _stacks(
    *,
    lane: str = "pr/900",
    parent_pr: int | None = 890,
    depth: int | None = 2,
    root: str | None = "pr/720",
    restack: bool = False,
) -> dict:
    return {
        lane: {
            "lane": lane,
            "pr": int(lane[3:]),
            "stack_root": root,
            "parent_pr": parent_pr,
            "depth": depth,
            "restack_required": restack,
        }
    }


def _mc_live(**kw) -> dict:
    packet = _mc(**kw)
    packet["repository"] = REPO
    packet["freshness"] = {"state": "LIVE", "age_seconds": 3, "max_age_seconds": 120}
    packet["attention"] = [
        {
            "attention_id": "att-1",
            "kind": "BLOCKED_HIGH_VALUE",
            "tier": 2,
            "summary": "pr/900 blocked",
            "references": [{"kind": "action_id", "id": "pr/900:OWNERSHIP_CLAIM"}],
        },
        {
            "attention_id": "att-2",
            "kind": "OWNER_DECISION",
            "tier": 1,
            "summary": "other lane",
            "references": [{"kind": "action_id", "id": "pr/901:OWNERSHIP_CLAIM"}],
        },
    ]
    return packet


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _seed_decisions_vault(vault: Path, project: str = "proj") -> None:
    (vault / "state" / "human-decisions").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    (vault / "state" / "human-decisions" / f"{project}.json").write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "review_id": "review-decision",
                        "decision": "accept",
                        "category": "pending-claim",
                        "subject_id": "claim-decision",
                        "reason": "owner accepted",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (vault / "state" / "claims" / f"{project}.json").write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "claim-decision",
                        "claim_type": "decision",
                        "value": "Prefer package data schemas",
                        "verification": "accepted",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


# --- packet shape, honesty, missing ------------------------------------------


def test_all_missing_packet_is_explicit_and_valid():
    p = tc.build_task_context(lane="pr/900", clock=clock)
    assert tc.validate_task_context(p) == []
    assert p["missing"] == [
        "NO_AGENT_BOUND",
        "NO_FRONTIER_MATRIX",
        "NO_MISSION_CONTROL",
        "NO_STACKS",
        "NO_VAULT_BOUND",
    ]
    assert p["lane_state"]["status"] == "UNKNOWN"
    assert p["freshness"]["state"] == "UNKNOWN"
    assert p["knowledge"]["state"] == "UNAVAILABLE"
    assert p["next_step"]["status"] == "NO_SUPPORTED_ACTION"
    assert p["next_step"]["authorization"] == "NOT_GRANTED_BY_THIS_PACKET"
    assert all(v is True for v in p["honesty"].values())


@pytest.mark.parametrize("bad", ["", "900", "pr/0", "pr/abc", "main"])
def test_invalid_lane_refused(bad):
    with pytest.raises(tc.TaskContextError, match="LANE_INVALID"):
        tc.build_task_context(lane=bad, clock=clock)


def test_full_join_success_path():
    matrix = _matrix(
        [
            _claim_action(),
            _claim_action(pr=901, runnable="BLOCKED", eligible=False, blockers=["OWNED_BY_OTHER"]),
        ]
    )
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=matrix,
        stacks=_stacks(),
        clock=clock,
    )
    assert tc.validate_task_context(p) == []
    ls = p["lane_state"]
    assert ls["status"] == "KNOWN"
    assert ls["identity"] == {
        "pr": 900,
        "head": HEAD,
        "tree": TREE,
        "ownership": "UNOWNED",
        "owner": None,
        "frozen": False,
        "ci_status": None,
        "iv_status": None,
    }
    assert ls["stack"] == {
        "status": "KNOWN",
        "stack_root": "pr/720",
        "parent_pr": 890,
        "depth": 2,
        "restack_required": False,
    }
    assert ls["implementation_vs_main"]["state"] == "OPEN_LANE_STACKED_DEPTH_2_NOT_ON_MAIN"
    assert ls["implementation_vs_main"]["merged"] == "UNKNOWN"
    assert {d["kind"] for d in ls["dependencies"]} == {"parent_pr", "stack_root"}
    assert p["freshness"]["state"] == "LIVE" and p["freshness"]["reasons"] == []
    assert [a["attention_id"] for a in p["attention"]] == ["att-1"]  # other lane filtered out
    assert p["repository"] == REPO
    assert "NO_VAULT_BOUND" in p["missing"] and "NO_FRONTIER_MATRIX" not in p["missing"]


def test_lane_absent_from_frontier_is_unknown_not_unowned():
    p = tc.build_task_context(
        lane="pr/777",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks={},
        clock=clock,
    )
    assert p["lane_state"]["status"] == "UNKNOWN"
    assert p["lane_state"]["identity"]["ownership"] == "UNKNOWN"
    assert "LANE_NOT_IN_FRONTIER" in p["missing"]
    assert any(r["condition"] == "LANE_UNKNOWN" for r in p["recovery"])


# --- freshness explanations ---------------------------------------------------


def test_stale_mission_control_is_explained_and_recovery_named():
    mc = _mc_live()
    mc["freshness"]["state"] = "STALE"
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=mc,
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        clock=clock,
    )
    assert p["freshness"]["state"] == "STALE"
    assert "MISSION_CONTROL_STALE" in p["freshness"]["reasons"]
    assert any(r["condition"] == "FRESHNESS_STALE" for r in p["recovery"])


def test_diverged_frontier_fingerprint_makes_live_stale():
    matrix = _matrix([_claim_action()])
    matrix["frontier_fingerprint"] = _fp("other")
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=matrix,
        stacks=_stacks(),
        clock=clock,
    )
    assert p["freshness"]["state"] == "STALE"
    assert "FRONTIER_FINGERPRINT_DIVERGED_FROM_MISSION_CONTROL" in p["freshness"]["reasons"]


# --- knowledge lenses (real project_atlas builders + injected classification) --


def test_empty_vault_is_unknown_not_healthy_and_untouched(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    before = _tree_hash(vault)
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="proj",
        clock=clock,
    )
    kn = p["knowledge"]
    assert kn["state"] in {"UNKNOWN", "KNOWN"}  # empty vault must never be CONFLICT/STALE
    assert set(kn["lenses"]) == {"state", "decisions", "unknown"}
    assert kn["lenses"]["state"]["state"] == "UNKNOWN"
    assert kn["lenses"]["decisions"]["state"] == "UNKNOWN"
    for lens in kn["lenses"].values():
        assert lens["provenance"]["authority"] is False
    assert _tree_hash(vault) == before  # read-only: no materialization
    assert "NO_VAULT_BOUND" not in p["missing"]


def test_seeded_decisions_are_known_with_sample(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_decisions_vault(vault)
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="proj",
        clock=clock,
    )
    dec = p["knowledge"]["lenses"]["decisions"]
    assert dec["state"] == "KNOWN"
    assert dec["counts"]["decision_count"] >= 1
    titles = {d.get("title") for d in dec["decisions_sample"]}
    assert "Prefer package data schemas" in titles
    assert p["knowledge"]["state"] == "KNOWN"


def test_conflict_and_stale_classification_via_injected_lenses(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    builders = {
        "state": lambda v, pid: {"status": "derived", "summary": "s", "stale_claims": 2},
        "decisions": lambda v, pid: {"status": "derived", "decision_count": 1, "decisions": []},
        "unknown": lambda v, pid: {
            "status": "derived",
            "unresolved_conflicts": [{"a": 1}],
            "unknown_items": ["x"],
        },
    }
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="proj",
        lens_builders=builders,
        clock=clock,
    )
    kn = p["knowledge"]
    assert kn["lenses"]["state"]["state"] == "STALE"
    assert kn["lenses"]["unknown"]["state"] == "CONFLICT"
    assert kn["lenses"]["decisions"]["state"] == "KNOWN"
    assert kn["state"] == "CONFLICT"  # conflict dominates
    assert any(r["condition"] == "KNOWLEDGE_CONFLICT" for r in p["recovery"])
    assert tc.validate_task_context(p) == []


def test_lens_exception_is_unavailable_not_guessed(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    def boom(v, pid):
        raise OSError("disk gone")

    builders = {"state": boom, "decisions": boom, "unknown": boom}
    p = tc.build_task_context(
        lane="pr/900",
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="proj",
        lens_builders=builders,
        clock=clock,
    )
    assert p["knowledge"]["state"] == "UNAVAILABLE"
    assert all(
        lens["state"] == "UNAVAILABLE" and "OSError" in lens["reason"]
        for lens in p["knowledge"]["lenses"].values()
    )


def test_vault_without_project_id_is_unavailable(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    p = tc.build_task_context(lane="pr/900", vault=vault, clock=clock)
    assert p["knowledge"] == {
        "state": "UNAVAILABLE",
        "reason": "NO_PROJECT_ID",
        "lenses": {},
        "provenance": {"authority": False},
    }
    assert "NO_PROJECT_ID" in p["missing"]


# --- next step + prerequisites -----------------------------------------------


def test_next_step_claim_prerequisites_and_preview_only():
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        clock=clock,
    )
    nxt = p["next_step"]
    assert nxt["status"] == "SUPPORTED"
    assert nxt["action"]["action_id"] == "pr/900:OWNERSHIP_CLAIM"
    assert {
        "CLAIM_INTENT_MINTED_FROM_LIVE_MISSION_CONTROL",
        "EXPLICIT_REPO_PIN_AT_EXECUTE",
        "CONTROL_PLANE_REVALIDATION_AT_EXECUTE",
    } <= set(nxt["prerequisites"])
    assert nxt["preview_command"].startswith("atlas-studio claim-preview")
    assert "claim-execute" not in nxt["preview_command"]
    assert nxt["authorization"] == "NOT_GRANTED_BY_THIS_PACKET"


def test_next_step_blocked_when_owned_by_other_or_not_runnable():
    owned = _claim_action(ownership="OWNED", owner="someone-else")
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([owned]),
        stacks=_stacks(),
        clock=clock,
    )
    assert "LANE_OWNED_BY_OTHER:someone-else" in p["next_step"]["prerequisites"]
    assert p["lane_state"]["owned_by_agent"] is False
    blocked = _claim_action(runnable="BLOCKED", eligible=False, blockers=["FROZEN_LANE"])
    q = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([blocked]),
        stacks=_stacks(),
        clock=clock,
    )
    assert q["next_step"]["status"] == "NO_SUPPORTED_ACTION"
    assert q["next_step"]["reasons"] == ["FROZEN_LANE"]
    assert q["lane_state"]["blockers"] == ["FROZEN_LANE"]


def test_owned_by_agent_flag_true_only_for_exact_owner():
    mine = _claim_action(ownership="OWNED", owner=AGENT)
    p = tc.build_task_context(
        lane="pr/900", agent_id=AGENT, frontier_matrix=_matrix([mine]), clock=clock
    )
    assert p["lane_state"]["owned_by_agent"] is True
    q = tc.build_task_context(
        lane="pr/900", agent_id=None, frontier_matrix=_matrix([mine]), clock=clock
    )
    assert q["lane_state"]["owned_by_agent"] is False


# --- continuation ------------------------------------------------------------


def test_continuation_points_to_existing_handoff_machinery_and_builds_nothing(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="proj",
        clock=clock,
    )
    c = p["continuation"]
    assert c["coordination_handoff"]["command"] == "atlas-dag handoff 900 --mode resume"
    assert c["coordination_handoff"]["built_here"] is False
    assert (
        c["knowledge_handoff"]["command"] == f"atlas handoff create --vault {vault} --project proj"
    )
    assert c["knowledge_handoff"]["built_here"] is False
    assert c["agent_context"] == {"status": "NOT_REQUESTED"}
    assert c["fingerprints"]["lane_head"] == HEAD
    assert c["fingerprints"]["mission_control"] == _mc_live()["snapshot_fingerprint"]
    assert len(c["fingerprint"]) == 64


def test_agent_context_export_is_optional_and_injected(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    calls: list[tuple] = []

    def fake_export(v, pid, *, refresh_brief=True):
        calls.append((v, pid, refresh_brief))
        return {
            "status": "exported",
            "next": ["do x"],
            "json_path": "ctx.json",
            "markdown_path": "ctx.md",
            "freshness": {"state": "LIVE"},
            "lens_is_authority": False,
        }

    p = tc.build_task_context(
        lane="pr/900",
        vault=vault,
        project_id="proj",
        include_agent_context=True,
        agent_context_fn=fake_export,
        clock=clock,
    )
    assert calls == [(vault, "proj", False)]  # never refreshes (no materialization)
    assert p["continuation"]["agent_context"]["status"] == "exported"
    assert p["continuation"]["agent_context"]["lens_is_authority"] is False
    q = tc.build_task_context(lane="pr/900", include_agent_context=True, clock=clock)
    assert q["continuation"]["agent_context"] == {
        "status": "UNAVAILABLE",
        "reason": "NO_VAULT_BOUND",
    }
    assert "AGENT_CONTEXT_NO_VAULT" in q["missing"]


# --- read-only + boundaries ---------------------------------------------------


def test_inputs_are_not_mutated():
    mc = _mc_live()
    matrix = _matrix([_claim_action()])
    stacks = _stacks()
    snap = (copy.deepcopy(mc), copy.deepcopy(matrix), copy.deepcopy(stacks))
    tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=mc,
        frontier_matrix=matrix,
        stacks=stacks,
        clock=clock,
    )
    assert (mc, matrix, stacks) == snap


def test_deterministic_fingerprint_excludes_clock():
    kw = dict(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
    )
    a = tc.build_task_context(**kw, clock=lambda: "2026-01-01T00:00:00Z")
    b = tc.build_task_context(**kw, clock=lambda: "2026-02-02T00:00:00Z")
    assert a["fingerprint"] == b["fingerprint"]


def test_module_has_no_mutation_imports_and_a1_untouched():
    src = Path(tc.__file__).read_text(encoding="utf-8")
    for token in (
        "emit_event",
        "execute_governed",
        "run_gh",
        "from atlas_studio import action_intent",
        "from atlas_studio import governance",
    ):
        assert token not in src, token
    from atlas_studio import mission_control as mc_mod

    mc_src = Path(mc_mod.__file__).read_text(encoding="utf-8")
    assert "task_context" not in mc_src


# --- CLI ---------------------------------------------------------------------


def _write_json(path: Path, obj: dict) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_cli_offline_files_json(tmp_path, capsys):
    rc = studio_cli.main(
        [
            "task-context",
            "--lane",
            "pr/900",
            "--agent",
            AGENT,
            "--mc-file",
            _write_json(tmp_path / "mc.json", _mc_live()),
            "--matrix-file",
            _write_json(tmp_path / "m.json", _matrix([_claim_action()])),
            "--stacks-file",
            _write_json(tmp_path / "s.json", _stacks()),
            "--json",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["schema"] == tc.SCHEMA_CONST
    assert out["lane_state"]["status"] == "KNOWN"
    assert out["knowledge"]["state"] == "UNAVAILABLE"


def test_cli_live_requires_agent(capsys):
    rc = studio_cli.main(["task-context", "--lane", "pr/900"])
    assert rc == 2
    assert "--agent" in capsys.readouterr().err


def test_cli_live_path_uses_shared_frontier_helper(monkeypatch, capsys):
    seen: list[tuple] = []

    def fake_live(agent_id, *, repo, clock=None):
        seen.append((agent_id, repo))
        return _mc_live(), _matrix([_claim_action()]), object(), _stacks()

    monkeypatch.setattr(studio_cli, "_live_frontier", fake_live)
    rc = studio_cli.main(["task-context", "--lane", "pr/900", "--agent", AGENT, "--repo", REPO])
    out = capsys.readouterr().out
    assert rc == 0 and seen == [(AGENT, REPO)]
    assert out.startswith("TASK CONTEXT pr/900")
    assert "NEXT_STEP!=AUTHORIZATION" in out


def test_claim_commands_still_get_three_tuple(monkeypatch):
    monkeypatch.setattr(
        studio_cli,
        "_live_frontier",
        lambda a, *, repo, clock=None: ("mc", "matrix", "registry", "stacks"),
    )
    assert studio_cli._live_claim_context(AGENT, repo=None) == ("mc", "matrix", "registry")


def test_doctor_reports_task_context_check(capsys):
    rc = studio_cli.main(["doctor", "--json"])
    report = json.loads(capsys.readouterr().out)
    checks = {c["name"]: c for c in report["checks"]}
    assert checks["a2_003_task_context"]["ok"] is True, checks["a2_003_task_context"]
    assert rc == 0


# --- real-lens shape (regression: injected fixtures hid a nested-signals bug) --


def _seed_conflict_vault(vault: Path, project: str = "harbor-api") -> None:
    """Real shapes the Coder Alpha lenses read: review/conflicts/<p>.json entries."""
    (vault / "review" / "conflicts").mkdir(parents=True, exist_ok=True)
    (vault / "review" / "conflicts" / f"{project}.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "conflict_id": "cf-1",
                        "subject": "deployment target",
                        "status": "pending",
                        "positions": [
                            {"source": "docs/plan.md", "value": "Kubernetes"},
                            {"source": "README.md", "value": "bare metal"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_real_lens_nested_signals_are_classified_not_ignored(tmp_path):
    """The real lenses nest counters under `signals`; a top-level-only reader is blind.

    Uses the real project_atlas builders over a real vault, so an injected-shape
    change in the lenses cannot silently make this pass again.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_conflict_vault(vault)
    before = _tree_hash(vault)
    p = tc.build_task_context(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        vault=vault,
        project_id="harbor-api",
        clock=clock,
    )
    kn = p["knowledge"]
    assert kn["state"] == "CONFLICT", kn
    assert kn["lenses"]["unknown"]["state"] == "CONFLICT"
    assert kn["lenses"]["unknown"]["counts"]["unresolved_conflicts"] == 1
    assert any(r["condition"] == "KNOWLEDGE_CONFLICT" for r in p["recovery"])
    assert _tree_hash(vault) == before
    assert tc.validate_task_context(p) == []


def test_signal_helper_prefers_signals_then_top_level():
    assert tc._signal({"signals": {"x": 5}, "x": 1}, "x") == 5
    assert tc._signal({"x": 1}, "x") == 1
    assert tc._signal({"signals": {}}, "x") is None
    assert tc._signal({"signals": "not-a-dict", "x": 2}, "x") == 2


def test_live_frontier_never_passes_none_clock_to_builders(monkeypatch):
    """Baseline defect: build_studio_snapshot calls clock() unconditionally."""
    seen: dict = {}

    def fake_mc(*, agent_id, live, repo, clock=None, **kw):
        seen["mc_clock"] = clock
        return _mc_live()

    def fake_matrix(snapshot, *, agent_id=None, registry=None, stacks=None, clock=None, **kw):
        seen["matrix_clock"] = clock
        seen["positional_only_snapshot"] = snapshot
        return _matrix([_claim_action()])

    monkeypatch.setattr("atlas_studio.mission_control.build_mission_control", fake_mc)
    monkeypatch.setattr("atlas_dag.frontier_matrix.build_frontier_matrix", fake_matrix)
    monkeypatch.setattr(
        "atlas_dag.model.build_snapshot", lambda client: {"nodes": [], "main_branch": "main"}
    )
    monkeypatch.setattr("atlas_dag.stack.build_stacks", lambda nodes, client, branch: _stacks())
    monkeypatch.setattr("atlas_dag.agents.load_registry", lambda: object())
    monkeypatch.setattr("atlas_dag.gh.GhClient", lambda repo=None: object())

    studio_cli._live_frontier(AGENT, repo=REPO)
    assert callable(seen["mc_clock"]), "None clock would raise inside build_studio_snapshot"
    assert callable(seen["matrix_clock"])
    assert isinstance(seen["positional_only_snapshot"], dict)


# --- continuation verification (export -> import -> verdict) ------------------


def _packet(**kw):
    base = dict(
        lane="pr/900",
        agent_id=AGENT,
        mission_control=_mc_live(),
        frontier_matrix=_matrix([_claim_action()]),
        stacks=_stacks(),
        clock=clock,
    )
    base.update(kw)
    return tc.build_task_context(**base)


def test_unchanged_truth_is_still_valid():
    rec = _packet()
    v = tc.verify_continuation(rec, _packet(), clock=clock)
    assert v["verdict"] == tc.STILL_VALID
    assert v["reasons"] == [] and v["changes"] == []
    assert v["authorization"] == "NOT_GRANTED_BY_THIS_PACKET"
    assert v["honesty"]["imported_context_ne_permission"] is True
    assert "not permission" in v["guidance"]
    assert tc.validate_continuation_verdict(v) == []


def test_moved_head_invalidates():
    rec = _packet()
    moved = _packet(frontier_matrix=_matrix([_claim_action(head="f" * 40)]))
    v = tc.verify_continuation(rec, moved, clock=clock)
    assert v["verdict"] == tc.INVALIDATED
    assert "LANE_HEAD_MOVED" in v["reasons"]
    change = next(c for c in v["changes"] if c["field"] == "lane_head")
    assert change["recorded"] == HEAD and change["current"] == "f" * 40
    assert "Rebuild task context" in v["guidance"]
    assert tc.validate_continuation_verdict(v) == []


def test_ownership_change_invalidates():
    rec = _packet()
    taken = _packet(
        frontier_matrix=_matrix([_claim_action(ownership="OWNED", owner="windows-main")])
    )
    v = tc.verify_continuation(rec, taken, clock=clock)
    assert v["verdict"] == tc.INVALIDATED
    assert {"OWNERSHIP_CHANGED", "OWNER_CHANGED"} <= set(v["reasons"])


def test_fingerprint_drift_is_advisory_not_invalidating():
    """The estate snapshot moves constantly; identity is what decides the verdict.

    Found live: two consecutive exports of the same unchanged lane differed in
    both fingerprints, so treating drift as INVALIDATED made every freshly
    exported packet invalid.
    """
    rec = _packet()
    matrix = _matrix([_claim_action()])
    matrix["frontier_fingerprint"] = _fp("moved-on")
    v = tc.verify_continuation(rec, _packet(frontier_matrix=matrix), clock=clock)
    assert v["verdict"] == tc.STILL_VALID
    assert v["changes"] == []
    codes = {c["code"] for c in v["advisory_changes"]}
    assert "FRONTIER_FINGERPRINT_CHANGED" in codes
    assert "REFUSED_STALE" in v["guidance"]
    assert tc.validate_continuation_verdict(v) == []


def test_identity_change_outranks_advisory_drift():
    rec = _packet()
    matrix = _matrix([_claim_action(head="f" * 40)])
    matrix["frontier_fingerprint"] = _fp("moved-on")
    v = tc.verify_continuation(rec, _packet(frontier_matrix=matrix), clock=clock)
    assert v["verdict"] == tc.INVALIDATED
    assert [c["code"] for c in v["changes"]] == ["LANE_HEAD_MOVED"]
    assert {c["code"] for c in v["advisory_changes"]} == {"FRONTIER_FINGERPRINT_CHANGED"}


def test_missing_current_truth_is_unverifiable_not_valid():
    v = tc.verify_continuation(_packet(), None, clock=clock)
    assert v["verdict"] == tc.UNVERIFIABLE
    assert v["reasons"] == ["CURRENT_TRUTH_UNAVAILABLE"]
    assert tc.validate_continuation_verdict(v) == []


@pytest.mark.parametrize("junk", ["not a dict", 42, None, []])
def test_non_packet_is_unverifiable(junk):
    v = tc.verify_continuation(junk, _packet(), clock=clock)
    assert v["verdict"] == tc.UNVERIFIABLE
    assert v["reasons"] == ["RECORDED_NOT_OBJECT"]


def test_schema_invalid_packet_is_unverifiable():
    bad = _packet()
    del bad["honesty"]
    v = tc.verify_continuation(bad, _packet(), clock=clock)
    assert v["verdict"] == tc.UNVERIFIABLE
    assert v["reasons"][0] == "RECORDED_SCHEMA_INVALID"


def test_unknown_side_is_unverifiable_never_silently_valid():
    """A field present on one side and absent on the other must not read as equal."""
    rec = _packet()
    blind = _packet(frontier_matrix=None)
    v = tc.verify_continuation(rec, blind, clock=clock)
    assert v["verdict"] in {tc.INVALIDATED, tc.UNVERIFIABLE}
    assert v["verdict"] != tc.STILL_VALID


def test_cli_verify_continuation_roundtrip(tmp_path, capsys):
    """Export a packet, then import it through the CLI and get a verdict."""
    pkt = tmp_path / "ctx.json"
    pkt.write_text(json.dumps(_packet()), encoding="utf-8")
    files = {
        "--mc-file": _write_json(tmp_path / "mc.json", _mc_live()),
        "--matrix-file": _write_json(tmp_path / "m.json", _matrix([_claim_action()])),
        "--stacks-file": _write_json(tmp_path / "s.json", _stacks()),
    }
    argv = ["task-context", "--verify-continuation", str(pkt), "--agent", AGENT]
    for flag, path in files.items():
        argv += [flag, path]
    rc = studio_cli.main([*argv, "--json"])
    verdict = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert verdict["schema"] == tc.VERDICT_SCHEMA_CONST
    assert verdict["verdict"] == tc.STILL_VALID
    assert verdict["recorded"]["lane"] == "pr/900"  # lane recovered from the packet


def test_cli_verify_continuation_exit_1_when_invalidated(tmp_path, capsys):
    pkt = tmp_path / "ctx.json"
    pkt.write_text(json.dumps(_packet()), encoding="utf-8")
    argv = [
        "task-context",
        "--verify-continuation",
        str(pkt),
        "--agent",
        AGENT,
        "--mc-file",
        _write_json(tmp_path / "mc.json", _mc_live()),
        "--matrix-file",
        _write_json(tmp_path / "m.json", _matrix([_claim_action(head="e" * 40)])),
        "--stacks-file",
        _write_json(tmp_path / "s.json", _stacks()),
    ]
    rc = studio_cli.main(argv)
    out = capsys.readouterr().out
    assert rc == 1
    assert "CONTINUATION INVALIDATED" in out
    assert "LANE_HEAD_MOVED" in out
    assert "IMPORTED_CONTEXT!=PERMISSION" in out


def test_cli_unreadable_packet_fails_closed(tmp_path, capsys):
    missing = tmp_path / "nope.json"
    rc = studio_cli.main(["task-context", "--verify-continuation", str(missing)])
    assert rc == 1
    assert "cannot read continuation packet" in capsys.readouterr().err


def test_cli_requires_lane_or_packet(capsys):
    rc = studio_cli.main(["task-context", "--agent", AGENT])
    assert rc == 2
    assert "--lane is required" in capsys.readouterr().err
