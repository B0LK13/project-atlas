"""AS-STUDIO-A1-001 — adversarial semantic boundary attacks (fail-closed).

STUDIO_UI != AUTHORITY
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1
AGENT_MATRIX_MISMATCH → DEGRADED (foreign frontier suppressed)
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import atlas_studio  # noqa: E402
from atlas_studio import mission_control as mc  # noqa: E402
from atlas_studio import snapshot as studio_snap  # noqa: E402

# Reuse A1 builders (do not invent mutation APIs).
from test_atlas_studio_a1_mission_control import (  # noqa: E402
    FORBIDDEN_API_NAMES,
    _fp,
    build_a0,
    build_mc,
    clock,
    injected_control_view,
    injected_matrix,
    injected_residuals,
)

AUTH_TRUE_KEYS = (
    "authorized",
    "permitted",
    "executable",
    "authorization_granted",
    "mutation_authorized",
)


# --- 1. attention ≠ authorization -------------------------------------------


def test_highest_ranked_attention_item_is_not_authorized():
    """Highest-ranked / attention item is NOT treated as authorized."""
    packet = build_mc(frontier_matrix=injected_matrix())
    assert packet["attention"], "expected attention items for matrix injection"
    assert packet["honesty"]["attention_ne_authorization"] is True
    top = packet["attention"][0]
    assert top["attention_ne_authorization"] is True
    for item in packet["attention"]:
        assert item.get("attention_ne_authorization") is True
        for key in AUTH_TRUE_KEYS:
            assert item.get(key) is not True, f"{key} true on attention"
    # Validation rejects forged authorization flags on attention.
    forged = dict(packet)
    forged["attention"] = [dict(top)]
    forged["attention"][0]["authorized"] = True
    errors = mc.validate_mission_control(forged)
    assert any("authorized" in e and "attention" in e for e in errors), errors


# --- 2. stale ≠ healthy -----------------------------------------------------


def test_stale_mission_control_cannot_validate_as_healthy():
    """freshness.state=STALE cannot have mission_status=HEALTHY and validate."""
    packet = build_mc(
        clock=lambda: "2026-09-09T12:00:00Z",
        now_clock=lambda: "2026-09-09T12:05:00Z",
        max_age_seconds=120,
    )
    assert packet["freshness"]["state"] == "STALE"
    assert packet["mission_status"] == "STALE"
    assert packet["mission_status"] != "HEALTHY"
    forced = dict(packet)
    forced["mission_status"] = "HEALTHY"
    errors = mc.validate_mission_control(forced)
    assert any("HEALTHY" in e and "LIVE" in e for e in errors), errors
    assert mc.validate_mission_control(packet) == []


# --- 3. UNKNOWN seal/evidence ≠ HEALTHY -------------------------------------


def test_unknown_seal_evidence_cannot_validate_as_healthy():
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


# --- 4. foreign agent_id / matrix mismatch ----------------------------------


def test_foreign_agent_matrix_cannot_fabricate_frontier():
    """Injected foreign agent_id/matrix cannot fabricate another agent's frontier.

    Fail-closed behavior (documented): when ``agent_id`` is set and the
    injected matrix declares a different ``agent``, frontier status becomes
    DEGRADED with ``AGENT_MATRIX_MISMATCH``; rankings/action_classes are
    suppressed (None); attention does not emit matrix-gate items from the
    foreign frontier; HEALTHY validation fails under mismatch notes.
    """
    foreign = injected_matrix()
    foreign = dict(foreign)
    foreign["agent"] = "foreign-agent-x"
    foreign["frontier_fingerprint"] = _fp("foreign-matrix")
    packet = build_mc(agent_id="agent-a", frontier_matrix=foreign)
    frontier = packet["views"]["frontier"]
    assert frontier["status"] == "DEGRADED"
    assert "AGENT_MATRIX_MISMATCH" in frontier["notes"]
    assert frontier["action_classes"]["by_action_class"] is None
    assert frontier["rankings"]["typed_rankings"] is None
    assert frontier["frontier_fingerprint"] is None
    attn_ids = [a["attention_id"] for a in packet["attention"]]
    assert not any(i.startswith("matrix-gate:") for i in attn_ids)
    assert not any(i.startswith("blocked-hv:") for i in attn_ids)
    assert packet["mission_status"] != "HEALTHY"
    forced = dict(packet)
    forced["mission_status"] = "HEALTHY"
    forced["freshness"] = dict(forced["freshness"])
    forced["freshness"]["state"] = "LIVE"
    errors = mc.validate_mission_control(forced)
    assert any("AGENT_MATRIX_MISMATCH" in e or "HEALTHY" in e for e in errors), errors


# --- 5. nested dishonest control_view (A0 path) -----------------------------


def test_nested_dishonest_control_view_cannot_yield_ok_healthy():
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
    assert any("honesty" in e.lower() or "HEALTHY" in e or "OK" in e for e in errors), (
        errors
    )


# --- 6. empty / malformed views ---------------------------------------------


def test_empty_or_malformed_views_fail_validation():
    packet = build_mc()
    empty = dict(packet)
    empty["views"] = dict(empty["views"])
    empty["views"]["health"] = {}
    errs_empty = mc.validate_mission_control(empty)
    assert any("health" in e for e in errs_empty), errs_empty

    malformed = dict(packet)
    malformed["views"] = dict(malformed["views"])
    malformed["views"]["frontier"] = {"summary": {"x": 1}}  # missing status+notes
    errs_mal = mc.validate_mission_control(malformed)
    assert any("frontier" in e for e in errs_mal), errs_mal

    non_object = dict(packet)
    non_object["views"] = dict(non_object["views"])
    non_object["views"]["telemetry"] = "not-a-view"  # type: ignore[assignment]
    errs_type = mc.validate_mission_control(non_object)
    assert any("telemetry" in e for e in errs_type), errs_type


# --- 7. no mutation symbols -------------------------------------------------


def test_no_mutation_symbols_in_atlas_studio_package():
    names = set(dir(mc)) | set(dir(atlas_studio)) | set(dir(studio_snap))
    for mod in (mc, atlas_studio, studio_snap):
        for name, obj in inspect.getmembers(mod):
            if name.startswith("_"):
                continue
            names.add(name)
            if inspect.isfunction(obj):
                names.add(obj.__name__)
    lowered = {n.lower() for n in names}
    for forbidden in FORBIDDEN_API_NAMES:
        assert forbidden not in lowered, f"forbidden API present: {forbidden}"

    pkg_root = REPO_ROOT / "scripts" / "atlas_studio"
    for path in sorted(pkg_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name.lower() not in FORBIDDEN_API_NAMES
                assert not node.name.lower().startswith("kill_")
                assert not node.name.lower().startswith("force_merge")
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
                assert not label.startswith("steal_write")


# --- 8. ranking projection = F12 typed_rankings (no re-rank) ----------------


def test_ranking_projection_equals_f12_typed_rankings_byte_for_byte():
    matrix = injected_matrix()
    # Deterministic but non-trivial rankings to prove byte-identical copy.
    matrix = dict(matrix)
    matrix["typed_rankings"] = {
        "best_write": ["pr/11:IMPLEMENT"],
        "best_readonly": [],
        "best_validation": ["pr/12:CI_DISPATCH"],
        "best_human_gate": ["pr/10:OWNER_DECISION"],
        "highest_value_blocker_removal": ["pr/11:IMPLEMENT", "pr/10:OWNER_DECISION"],
    }
    packet = build_mc(agent_id="agent-a", frontier_matrix=matrix)
    projected = packet["views"]["frontier"]["rankings"]["typed_rankings"]
    expected = dict(sorted(matrix["typed_rankings"].items()))
    assert projected == expected
    assert json.dumps(projected, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )
    assert "no_studio_re_rank" in packet["views"]["frontier"]["rankings"]["notes"]


# --- 9. no sticky authorize / fingerprint cache -----------------------------


def test_cached_old_fingerprint_two_builds_differ():
    """Two builds with different injected snapshots produce different fingerprints."""
    res_a = injected_residuals()
    res_b = dict(injected_residuals())
    res_b["registry_fingerprint"] = _fp("semantic-residuals-b")
    snap_a = build_a0(residual_registry=res_a)
    snap_b = build_a0(residual_registry=res_b)
    mc_a = mc.build_mission_control(studio_snapshot=snap_a, clock=clock)
    mc_b = mc.build_mission_control(studio_snapshot=snap_b, clock=clock)
    assert mc_a["snapshot_fingerprint"] != mc_b["snapshot_fingerprint"]
    matrix_a = injected_matrix()
    matrix_b = dict(injected_matrix())
    matrix_b["frontier_fingerprint"] = _fp("matrix-b-distinct")
    matrix_b["typed_rankings"] = dict(matrix_b["typed_rankings"])
    matrix_b["typed_rankings"]["best_write"] = ["pr/99:IMPLEMENT"]
    mc_m_a = build_mc(agent_id="agent-a", frontier_matrix=matrix_a)
    mc_m_b = build_mc(agent_id="agent-a", frontier_matrix=matrix_b)
    assert mc_m_a["snapshot_fingerprint"] != mc_m_b["snapshot_fingerprint"]


# --- 10. attention ordering deterministic -----------------------------------


def test_attention_ordering_deterministic_for_identical_inputs():
    matrix = injected_matrix()
    a = build_mc(frontier_matrix=matrix, agent_id="agent-a")
    b = build_mc(frontier_matrix=copy.deepcopy(matrix), agent_id="agent-a")
    ids_a = [x["attention_id"] for x in a["attention"]]
    ids_b = [x["attention_id"] for x in b["attention"]]
    assert ids_a == ids_b
    assert [x["kind"] for x in a["attention"]] == [x["kind"] for x in b["attention"]]
    # Tier order is non-decreasing (urgency sort contract).
    tiers = [int(x["tier"]) for x in a["attention"]]
    assert tiers == sorted(tiers)
