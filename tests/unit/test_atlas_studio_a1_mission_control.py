"""AS-STUDIO-A1-001 — Mission Control contracts.

STUDIO_UI != AUTHORITY
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import atlas_studio  # noqa: E402
from atlas_studio import mission_control as mc  # noqa: E402
from atlas_studio import snapshot as studio_snap  # noqa: E402

FIXED = "2026-09-09T12:00:00Z"
REPO = "B0LK13/project-atlas"

FORBIDDEN_API_NAMES = frozenset(
    {
        "claim",
        "dispatch",
        "emit",
        "merge",
        "mutate",
        "write_vault",
        "kill_daemon",
        "kill_agent",
        "terminate_agent",
        "terminate_task",
        "daemon_kill",
        "force_merge",
        "steal_write",
    }
)


def clock():
    return FIXED


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def injected_control_view(*, agent_status: str = "NONE"):
    from atlas_dag import control_view as cv_mod

    view = cv_mod.build_global_control_view(
        repository=REPO,
        clock=clock,
        seal_scan="skipped_for_latency",
        agent_id=None,
    )
    if agent_status != view.get("agent_status"):
        view = dict(view)
        view["agent_status"] = agent_status
    return view


def injected_telemetry(*, agent_status: str = "NONE"):
    from atlas_dag import telemetry as tel_mod

    packet = tel_mod.build_coordination_telemetry(
        repository=REPO,
        clock=clock,
        seal_projection="deferred_or_skipped",
        agent_id=None,
    )
    if agent_status != packet.get("agent_status"):
        packet = dict(packet)
        packet["agent_status"] = agent_status
    return packet


def injected_residuals():
    from atlas_dag import residuals as res_mod

    return res_mod.build_residual_registry(
        repository=REPO,
        clock=clock,
        events=[],
    )


def injected_matrix() -> dict:
    """Minimal F12-shaped matrix for injection (does not invent live eligibility)."""
    return {
        "schema": "ATLAS_MULTIDIMENSIONAL_FRONTIER_V1",
        "generated_at_utc": FIXED,
        "agent": "agent-a",
        "agent_status": "REGISTERED_ACTIVE",
        "actions": [
            {
                "action_id": "pr/10:OWNER_DECISION",
                "pr": 10,
                "action_type": "OWNER_DECISION",
                "action_class": "HUMAN_GATE",
                "runnable_state": "BLOCKED",
                "blocking_reasons": ["OWNER_DECISION_REQUIRES_HUMAN"],
                "agent_eligible": False,
                "truth_fingerprint": _fp("a1"),
            },
            {
                "action_id": "pr/11:IMPLEMENT",
                "pr": 11,
                "action_type": "IMPLEMENT",
                "action_class": "WRITE",
                "runnable_state": "BLOCKED",
                "blocking_reasons": ["WAITING_CI"],
                "agent_eligible": False,
                "truth_fingerprint": _fp("a2"),
                "score_total": 9.5,
            },
        ],
        "eligible_actions": [],
        "ineligible_actions": [],
        "blocked_actions": ["pr/10:OWNER_DECISION", "pr/11:IMPLEMENT"],
        "by_action_class": {
            "HUMAN_GATE": [],
            "READONLY": [],
            "VALIDATION": [],
            "WRITE": [],
        },
        "typed_rankings": {
            "best_write": [],
            "best_readonly": [],
            "best_validation": [],
            "best_human_gate": [],
            "highest_value_blocker_removal": ["pr/11:IMPLEMENT"],
        },
        "frontier_fingerprint": _fp("matrix-a1"),
        "parallel_runnable_set": [],
    }


def build_a0(**kwargs):
    defaults = {
        "repository": REPO,
        "control_view": injected_control_view(),
        "telemetry_packet": injected_telemetry(),
        "residual_registry": injected_residuals(),
        "clock": clock,
    }
    defaults.update(kwargs)
    return studio_snap.build_studio_snapshot(**defaults)


def build_mc(**kwargs):
    defaults = {
        "repository": REPO,
        "control_view": injected_control_view(),
        "telemetry_packet": injected_telemetry(),
        "residual_registry": injected_residuals(),
        "clock": clock,
    }
    defaults.update(kwargs)
    return mc.build_mission_control(**defaults)


def test_mc_schema_validates():
    packet = build_mc()
    errors = mc.validate_mission_control(packet)
    assert errors == [], errors
    assert packet["schema"] == "ATLAS_STUDIO_MISSION_CONTROL_V1"
    assert packet["honesty"]["attention_ne_authorization"] is True
    assert packet["honesty"]["stale_ne_current"] is True
    assert packet["honesty"]["unknown_ne_healthy"] is True
    assert packet["honesty"]["nested_honesty_fail_closed"] is True
    assert atlas_studio.O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME is True
    assert atlas_studio.O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN is True


def test_dishonest_nested_honesty_cannot_be_healthy_or_ok():
    cv = injected_control_view()
    cv = dict(cv)
    cv["honesty"] = dict(cv["honesty"])
    cv["honesty"]["control_view_ne_authority"] = False
    try:
        build_mc(control_view=cv)
        raise AssertionError("expected MissionControlError/StudioSnapshotError")
    except studio_snap.StudioSnapshotError as exc:
        assert "honesty" in str(exc).lower()

    packet = build_mc()
    packet = dict(packet)
    snap = dict(packet["studio_snapshot"])
    panels = dict(snap["panels"])
    cv_panel = dict(panels["control_view"])
    body = dict(cv_panel["body"])
    body["honesty"] = dict(body["honesty"])
    body["honesty"]["control_view_ne_authority"] = False
    cv_panel["body"] = body
    panels["control_view"] = cv_panel
    snap["panels"] = panels
    packet["studio_snapshot"] = snap
    packet["mission_status"] = "HEALTHY"
    packet["slice_status"] = "OK"
    errors = mc.validate_mission_control(packet)
    assert any("honesty" in e.lower() or "HEALTHY" in e or "OK" in e for e in errors), errors


def test_empty_panels_fail_schema():
    packet = build_mc()
    packet = dict(packet)
    packet["views"] = dict(packet["views"])
    packet["views"]["health"] = {}
    errors = mc.validate_mission_control(packet)
    assert any("health" in e for e in errors), errors


def test_action_classes_present_when_matrix_injected():
    matrix = injected_matrix()
    packet = build_mc(frontier_matrix=matrix)
    frontier = packet["views"]["frontier"]
    assert frontier["action_classes"]["status"] == "OK"
    assert frontier["action_classes"]["by_action_class"] == matrix["by_action_class"]
    assert frontier["rankings"]["status"] == "OK"
    assert (
        frontier["rankings"]["typed_rankings"]["highest_value_blocker_removal"]
        == ["pr/11:IMPLEMENT"]
    )
    assert "pr/10:OWNER_DECISION" in frontier["human_gate_action_ids"]
    assert "pr/10:OWNER_DECISION" in frontier["owner_decision_action_ids"]
    assert mc.validate_mission_control(packet) == []


def test_action_classes_unknown_when_matrix_absent_not_fake_healthy():
    packet = build_mc(frontier_matrix=None)
    frontier = packet["views"]["frontier"]
    assert frontier["status"] == "UNKNOWN"
    assert frontier["action_classes"]["status"] == "UNKNOWN"
    assert frontier["action_classes"]["by_action_class"] is None
    assert frontier["rankings"]["status"] == "UNKNOWN"
    assert frontier["rankings"]["typed_rankings"] is None
    assert "MATRIX_ABSENT" in frontier["notes"]
    assert frontier["action_classes"]["status"] != "OK"


def test_positive_f12_surfaces_human_gates_in_mc_view():
    packet = build_mc(frontier_matrix=injected_matrix())
    hg = packet["views"]["human_gates"]
    assert hg["summary"]["human_gate_count"] >= 1
    assert hg["summary"]["owner_decision_count"] >= 1
    kinds = {a["kind"] for a in packet["attention"]}
    assert "HUMAN_GATE" in kinds or "OWNER_DECISION" in kinds
    assert "BLOCKED_HIGH_VALUE" in kinds


def test_attention_ranking_deterministic_no_invented_eligibility():
    matrix = injected_matrix()
    a = build_mc(frontier_matrix=matrix)
    b = build_mc(frontier_matrix=matrix)
    assert [x["attention_id"] for x in a["attention"]] == [
        x["attention_id"] for x in b["attention"]
    ]
    bare = build_mc(frontier_matrix=None)
    ids = [x["attention_id"] for x in bare["attention"]]
    assert not any(i.startswith("matrix-gate:") for i in ids)
    assert not any(i.startswith("blocked-hv:") for i in ids)
    for item in a["attention"]:
        assert item["attention_ne_authorization"] is True


def test_stale_when_generated_at_older_than_max_age():
    packet = build_mc(
        clock=lambda: "2026-09-09T12:00:00Z",
        now_clock=lambda: "2026-09-09T12:05:00Z",
        max_age_seconds=120,
    )
    assert packet["freshness"]["state"] == "STALE"
    assert packet["freshness"]["age_seconds"] == 300.0
    assert packet["mission_status"] == "STALE"
    assert packet["freshness"]["state"] != "LIVE"


def test_unknown_seal_evidence_not_promoted_to_healthy():
    packet = build_mc()
    assert packet["views"]["postmerge_seal"]["status"] == "UNKNOWN"
    assert packet["views"]["evidence"]["status"] == "UNKNOWN"
    assert packet["mission_status"] != "HEALTHY"
    forced = dict(packet)
    forced["mission_status"] = "HEALTHY"
    forced["freshness"] = dict(forced["freshness"])
    forced["freshness"]["state"] = "LIVE"
    errors = mc.validate_mission_control(forced)
    assert any("HEALTHY" in e and "UNKNOWN" in e for e in errors), errors


def test_no_mutation_apis():
    names = set(dir(mc)) | set(dir(atlas_studio))
    for name, obj in inspect.getmembers(mc):
        if name.startswith("_"):
            continue
        names.add(name)
        if inspect.isfunction(obj):
            names.add(obj.__name__)
    lowered = {n.lower() for n in names}
    for forbidden in FORBIDDEN_API_NAMES:
        assert forbidden not in lowered, f"forbidden API present: {forbidden}"

    pkg_root = REPO_ROOT / "scripts" / "atlas_studio"
    for path in pkg_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                label = ""
                if isinstance(func, ast.Name):
                    label = func.id
                elif isinstance(func, ast.Attribute):
                    label = func.attr
                assert label not in FORBIDDEN_API_NAMES
                assert not label.startswith("kill_daemon")
                assert not label.startswith("force_merge")


def test_reconnect_rebuild_different_fingerprints_no_sticky_cache():
    res_a = injected_residuals()
    res_b = dict(injected_residuals())
    res_b["registry_fingerprint"] = _fp("different-residuals")
    snap_a = build_a0(residual_registry=res_a)
    snap_b = build_a0(residual_registry=res_b)
    mc_a = mc.build_mission_control(studio_snapshot=snap_a, clock=clock)
    mc_b = mc.build_mission_control(studio_snapshot=snap_b, clock=clock)
    assert mc_a["snapshot_fingerprint"] != mc_b["snapshot_fingerprint"]
    assert mc_a["studio_snapshot"]["snapshot_fingerprint"] != (
        mc_b["studio_snapshot"]["snapshot_fingerprint"]
    )


def test_freshness_live_when_age_within_max():
    packet = build_mc(
        clock=lambda: "2026-09-09T12:00:00Z",
        now_clock=lambda: "2026-09-09T12:01:00Z",
        max_age_seconds=120,
    )
    assert packet["freshness"]["state"] == "LIVE"
    assert packet["freshness"]["age_seconds"] == 60.0


def test_tui_formatter_includes_badges():
    text = mc.format_mission_control_tui(build_mc(frontier_matrix=injected_matrix()))
    assert "MISSION CONTROL" in text
    assert "ATTENTION" in text
    assert "action_classes=" in text
