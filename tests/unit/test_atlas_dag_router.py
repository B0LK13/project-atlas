"""Offline adversarial tests for the agent-aware work router (FEATURE_02).

Fail-closed matrix under test (D-ATLAS-DAG-FEATURE-02):
- unknown agent => NO_SAFE_ROUTE;
- inactive agent => NO_SAFE_ROUTE;
- invalid/missing registry => no route;
- Windows-native lane cannot route as write to a Linux agent;
- another owner's writable lane cannot route as write;
- frozen lane cannot route as write;
- OWNER/IV/POLICY-gated (non-RUNNABLE_WRITE) node cannot become writable;
- out-of-scope paths cannot become writable;
- formal-IV work cannot route merely because a profile says verifier;
- RUNNABLE_READONLY remains available when write is prohibited;
- one blocked lane does not suppress unrelated eligible work;
- duplicate/conflicting ownership fails closed (AMBIGUOUS never writes);
- output is deterministic across equivalent snapshot orderings.

Negative controls: each denial becomes routable only when the specific
legitimate constraint is removed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import agents as agents_mod  # noqa: E402
from atlas_dag import router as router_mod  # noqa: E402


def make_profile(**overrides) -> dict:
    profile = {
        "agent_id": "ubuntu-main",
        "role": "coordinator",
        "active": True,
        "platforms": ["linux"],
        "capabilities": [
            "READ_REPO", "READ_GITHUB", "WRITE_CODE", "WRITE_TESTS",
            "POST_EVENTS", "CLAIM_OWNERSHIP",
        ],
        "prohibitions": ["AUTO_MERGE", "SELF_IV", "BYPASS_OWNER_GATE",
                         "BYPASS_FREEZE"],
        "write_scopes": ["path:scripts/atlas_dag", "github:issue-comment:719"],
        "event_permissions": ["OWNER_CLAIMED", "HEAD_MOVED"],
        "verification_class": "IMPLEMENTATION",
        "principal": "github:B0LK13",
    }
    profile.update(overrides)
    return profile


def write_registry(tmp_path: Path, agents: list[dict]) -> agents_mod.RegistryResult:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "agents.json"
    path.write_text(json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1",
        "registry_id": "test-registry",
        "version": 1,
        "agents": agents,
    }), encoding="utf-8")
    return agents_mod.load_registry(path)


def make_node(lane: str, **overrides) -> dict:
    number = int(lane.split("/")[1])
    node = {
        "lane": lane,
        "pr": number,
        "state": "RUNNABLE_WRITE",
        "ownership": "OWNED",
        "owner": "ubuntu-main",
        "frozen": False,
        "head": "a" * 40,
    }
    node.update(overrides)
    return node


def snapshot_of(*nodes: dict) -> dict:
    return {"schema": "ATLAS_DAG_SNAPSHOT_V1", "nodes": list(nodes)}


@pytest.fixture
def env(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    return registry, snapshot_of(make_node("pr/700"))


# --- agent-level fail-closed -------------------------------------------------

def test_unknown_agent_no_safe_route(env):
    registry, _snapshot = env
    result = router_mod.route("ghost-agent", _snapshot, registry)
    assert result["action_class"] == router_mod.NO_ROUTE
    assert not result["routable"]
    assert result["agent_status"] == "UNKNOWN_AGENT"


def test_inactive_agent_no_safe_route(tmp_path):
    registry = write_registry(
        tmp_path, [make_profile(agent_id="windows-main", active=False,
                                platforms=["windows"])])
    snapshot = snapshot_of(make_node("pr/709", state="RUNNABLE_READONLY",
                                     ownership="UNOWNED", owner=None))
    result = router_mod.route("windows-main", snapshot, registry)
    assert result["action_class"] == router_mod.NO_ROUTE
    assert "AGENT_INACTIVE" in result["blockers"]


def test_missing_registry_no_route(tmp_path):
    result = router_mod.route(
        "ubuntu-main", snapshot_of(make_node("pr/700")),
        agents_mod.load_registry(tmp_path / "absent.json"))
    assert result["action_class"] == router_mod.NO_ROUTE
    assert result["agent_status"] == "REGISTRY_INVALID"


def test_invalid_registry_no_route(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1", "registry_id": "bad",
        "version": 1, "agents": [make_profile(capabilities=["FLY"])],
    }), encoding="utf-8")
    result = router_mod.route("ubuntu-main", snapshot_of(make_node("pr/700")),
                              agents_mod.load_registry(path))
    assert result["action_class"] == router_mod.NO_ROUTE


# --- lane-level filters with negative controls --------------------------------

def test_write_route_for_own_lane(env):
    registry, _snapshot = env
    result = router_mod.route("ubuntu-main", _snapshot, registry)
    assert result["action_class"] == router_mod.ROUTE_WRITE
    assert result["routable"] and result["lane"] == "pr/700"


def test_other_owner_lane_routes_readonly_only(env):
    registry, _snapshot = env
    node = make_node("pr/701", owner="windows-main")
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    lane = next(r for r in result["routes"] if r["lane"] == "pr/701")
    assert any("OWNERSHIP_MUTEX_HELD_BY:windows-main" in b
               for b in lane["blockers"])
    # negative control: same lane, mutex released to this agent => write
    fixed = make_node("pr/701")
    assert router_mod.route("ubuntu-main", snapshot_of(fixed),
                            registry)["action_class"] == router_mod.ROUTE_WRITE


def test_frozen_lane_routes_readonly_only(env):
    registry, _snapshot = env
    node = make_node("pr/702", frozen=True, state="FROZEN")
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    # negative control: unfrozen => write
    assert router_mod.route(
        "ubuntu-main", snapshot_of(make_node("pr/702")), registry
    )["action_class"] == router_mod.ROUTE_WRITE


def test_non_writable_snapshot_state_cannot_become_writable(env):
    """An OWNER/IV/POLICY-gated node (classifier says READONLY) stays so."""
    registry, _snapshot = env
    node = make_node("pr/703", state="RUNNABLE_READONLY",
                     ownership="UNOWNED", owner=None)
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    lane = result["routes"][0]
    assert any(b.startswith("SNAPSHOT_STATE_NOT_WRITABLE") for b in lane["blockers"])
    assert any(b == "LANE_UNOWNED_WRITE_REQUIRES_CLAIM" for b in lane["blockers"])


def test_windows_native_lane_cannot_route_as_write_to_linux(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    node = make_node("pr/709", platform_requirements=["windows"])
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    lane = result["routes"][0]
    assert any(b.startswith("PLATFORM_REQUIRED:windows") for b in lane["blockers"])
    # negative control: windows agent on windows lane => write
    win_registry = write_registry(tmp_path / "win", [make_profile(
        agent_id="windows-main", platforms=["windows"])])
    win_node = make_node("pr/709", owner="windows-main",
                         platform_requirements=["windows"])
    assert router_mod.route("windows-main", snapshot_of(win_node),
                            win_registry)["action_class"] == router_mod.ROUTE_WRITE


def test_out_of_scope_paths_cannot_become_writable(tmp_path):
    registry = write_registry(tmp_path, [make_profile(
        write_scopes=["path:docs"])])
    node = make_node("pr/704", required_scopes=["path:src/project_atlas"])
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    lane = result["routes"][0]
    assert any(b.startswith("SCOPE_NOT_COVERED") for b in lane["blockers"])
    # negative control: scope covered => write
    ok_registry = write_registry(tmp_path / "ok", [make_profile(
        write_scopes=["path:src"])])
    assert router_mod.route("ubuntu-main", snapshot_of(node),
                            ok_registry)["action_class"] == router_mod.ROUTE_WRITE


def test_verifier_profile_cannot_route_formal_iv_work(tmp_path):
    """A verifier-class profile routes like any other: formal IV is not a
    routable action class in v1 and never becomes writable work."""
    registry = write_registry(tmp_path, [make_profile(
        agent_id="independent-verifier", verification_class="INDEPENDENT_VERIFIER",
        role="independent verifier lane")])
    node = make_node("pr/705", owner="independent-verifier")
    result = router_mod.route("independent-verifier", snapshot_of(node), registry)
    # write still routes (the lane is theirs) but no IV action class exists
    assert result["action_class"] == router_mod.ROUTE_WRITE
    assert all(r["action_class"] != "FORMAL_IV" for r in result["routes"])
    # ...and a verifier without write capability on an IV-waiting lane gets
    # readonly, never an IV route
    read_only_registry = write_registry(tmp_path / "ro", [make_profile(
        agent_id="independent-verifier", verification_class="INDEPENDENT_VERIFIER",
        role="independent verifier lane",
        capabilities=["READ_REPO", "READ_GITHUB"])])
    assert router_mod.route("independent-verifier", snapshot_of(node),
                            read_only_registry)["action_class"] == \
        router_mod.ROUTE_READONLY


def test_ownership_ambiguous_fails_closed(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    node = make_node("pr/706", ownership="AMBIGUOUS",
                     owner=None, claimants=["ubuntu-main", "windows-main"])
    result = router_mod.route("ubuntu-main", snapshot_of(node), registry)
    assert result["action_class"] == router_mod.ROUTE_READONLY
    assert any("OWNERSHIP_AMBIGUOUS_FAIL_CLOSED" in b
               for b in result["routes"][0]["blockers"])
    # negative control: single owner resolves ambiguity => write
    assert router_mod.route("ubuntu-main", snapshot_of(make_node("pr/706")),
                            registry)["action_class"] == router_mod.ROUTE_WRITE


# --- selection semantics ------------------------------------------------------

def test_write_preferred_over_readonly_and_lane_tiebreak(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    nodes = [
        make_node("pr/710", state="RUNNABLE_READONLY", ownership="UNOWNED",
                  owner=None),
        make_node("pr/702", owner="ubuntu-main"),
        make_node("pr/701", owner="ubuntu-main"),
    ]
    result = router_mod.route("ubuntu-main", snapshot_of(*nodes), registry)
    assert result["action_class"] == router_mod.ROUTE_WRITE
    assert result["lane"] == "pr/701"  # canonical lane order tie-break
    classes = [r["action_class"] for r in result["routes"]]
    assert classes == sorted(classes, key={
        router_mod.ROUTE_WRITE: 0, router_mod.ROUTE_READONLY: 1}.get)


def test_blocked_lane_does_not_suppress_unrelated_lane(tmp_path):
    """Waiting is lane-local: one mutex/frozen lane never blocks another."""
    registry = write_registry(tmp_path, [make_profile()])
    nodes = [
        make_node("pr/711", owner="windows-main"),          # foreign owner
        make_node("pr/712", frozen=True, state="FROZEN"),   # frozen
        make_node("pr/713", owner="ubuntu-main"),           # mine
    ]
    result = router_mod.route("ubuntu-main", snapshot_of(*nodes), registry)
    assert result["lane"] == "pr/713"
    assert result["action_class"] == router_mod.ROUTE_WRITE


def test_no_safe_route_when_nothing_routable(tmp_path):
    registry = write_registry(
        tmp_path, [make_profile(capabilities=["POST_EVENTS"])])
    result = router_mod.route("ubuntu-main", snapshot_of(make_node("pr/700")),
                              registry)
    assert result["action_class"] == router_mod.NO_ROUTE
    assert "NO_READ_CAPABILITY" in result["routes"][0]["blockers"]


def test_determinism_across_equivalent_snapshot_orderings(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    nodes = [
        make_node("pr/720", owner="ubuntu-main"),
        make_node("pr/703", state="RUNNABLE_READONLY", ownership="UNOWNED",
                  owner=None),
        make_node("pr/701", owner="windows-main"),
    ]
    forward = router_mod.route("ubuntu-main", snapshot_of(*nodes), registry)
    reverse = router_mod.route("ubuntu-main", snapshot_of(*reversed(nodes)),
                               registry)
    assert json.dumps(forward, sort_keys=True) == json.dumps(reverse, sort_keys=True)
