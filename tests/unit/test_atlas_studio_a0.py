"""AS-STUDIO-A0-001 — Linux RO Studio vertical slice contracts.

STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
STUDIO_CRASH != AGENT_TASK_TERMINATION
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import atlas_studio  # noqa: E402
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
    }
)

FORBIDDEN_CRASH_KILL_SYMBOLS = frozenset(
    {
        "kill_daemon",
        "kill_agent",
        "terminate_agent_task",
        "terminate_daemon",
        "os.killpg",
        "daemon_kill",
        "stop_agent_runtime",
    }
)


def clock():
    return FIXED


def _fp(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode()).hexdigest()


def injected_control_view(*, agent_status: str = "NONE", panels: dict | None = None):
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
    if panels is not None:
        view = dict(view)
        merged = dict(view.get("panels") or {})
        merged.update(panels)
        view["panels"] = merged
        # fingerprint will not match body; validators may not check fingerprint sync
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



def build_injected(**kwargs):
    defaults = {
        "repository": REPO,
        "control_view": injected_control_view(),
        "telemetry_packet": injected_telemetry(),
        "residual_registry": injected_residuals(),
        "clock": clock,
    }
    defaults.update(kwargs)
    return studio_snap.build_studio_snapshot(**defaults)


# --- schema + honesty -------------------------------------------------------


def test_snapshot_schema_validates():
    packet = build_injected()
    errors = studio_snap.validate_studio_snapshot(packet)
    assert errors == [], errors
    assert packet["schema"] == "ATLAS_STUDIO_SNAPSHOT_V1"


def test_honesty_consts_true():
    packet = build_injected()
    h = packet["honesty"]
    assert h["studio_ui_ne_authority"] is True
    assert h["ui_state_is_projection"] is True
    assert h["grants_no_mutation"] is True
    assert h["no_cli_text_parsing_as_protocol"] is True
    assert atlas_studio.STUDIO_UI_NE_AUTHORITY is True
    assert atlas_studio.ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME is True
    assert atlas_studio.STUDIO_CRASH_NE_AGENT_TASK_TERMINATION is True


def test_observation_event_schema():
    ev = studio_snap.make_observation_event(
        event_id="e1",
        kind="OBSERVATION",
        clock=clock,
        message="probe",
    )
    assert studio_snap.validate_studio_event(ev) == []


# --- injection / no subprocess ---------------------------------------------


def test_uses_injected_control_view_and_telemetry_no_subprocess(monkeypatch):
    calls = {"popen": 0, "run": 0}

    def boom(*_a, **_k):
        calls["run"] += 1
        raise AssertionError("subprocess must not be used for Studio protocol")

    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.setattr("subprocess.Popen", boom)

    cv = injected_control_view(
        panels={
            "agents": {"status": "OK", "summary": {"n": 1}, "notes": []},
            "residuals": {"status": "OK", "summary": {"open": 2}, "notes": []},
        }
    )
    tel = injected_telemetry()
    packet = build_injected(control_view=cv, telemetry_packet=tel)
    assert packet["panels"]["control_view"]["body"] is cv
    assert packet["panels"]["telemetry"]["body"] is tel
    assert packet["panels"]["control_view"]["status"] == "OK"
    assert packet["panels"]["telemetry"]["status"] == "OK"
    assert calls["run"] == 0


def test_positive_residual_and_control_panels_when_injected():
    packet = build_injected()
    assert packet["panels"]["control_view"]["status"] == "OK"
    assert packet["panels"]["residuals"]["status"] == "OK"
    body = packet["panels"]["residuals"]["body"]
    assert "residual_count" in body["summary"]
    assert body["registry"]["schema"] == "ATLAS_RESIDUAL_REGISTRY_V1"


def test_nested_dishonest_control_view_honesty_fails_closed():
    cv = injected_control_view()
    cv = dict(cv)
    cv["honesty"] = dict(cv["honesty"])
    cv["honesty"]["control_view_ne_authority"] = False
    try:
        build_injected(control_view=cv)
        raise AssertionError("expected StudioSnapshotError")
    except studio_snap.StudioSnapshotError as exc:
        assert "honesty" in str(exc).lower()


def test_validate_rejects_empty_panel_objects():
    packet = build_injected()
    packet = dict(packet)
    packet["panels"] = dict(packet["panels"])
    packet["panels"]["control_view"] = {}
    errors = studio_snap.validate_studio_snapshot(packet)
    assert any("status" in e or "required" in e.lower() for e in errors), errors


def test_validate_rejects_ok_slice_with_unknown_panel():
    packet = build_injected()
    packet = dict(packet)
    packet["slice_status"] = "OK"
    packet["panels"] = dict(packet["panels"])
    packet["panels"]["telemetry"] = {
        "status": "UNKNOWN",
        "notes": ["forced"],
        "body": None,
    }
    errors = studio_snap.validate_studio_snapshot(packet)
    assert any(e.startswith("slice_status:") for e in errors), errors


def test_nested_control_view_validated_on_snapshot():
    packet = build_injected()
    assert studio_snap.validate_studio_snapshot(packet) == []
    from atlas_dag.control_view import validate_control_view

    assert validate_control_view(packet["panels"]["control_view"]["body"]) == []



# --- mutation / crash surface absent ----------------------------------------


def test_mutation_surfaces_absent():
    names = set(dir(studio_snap)) | set(dir(atlas_studio))
    # Also walk public callables on snapshot module
    for name, obj in inspect.getmembers(studio_snap):
        if name.startswith("_"):
            continue
        names.add(name)
        if inspect.isfunction(obj):
            names.add(obj.__name__)
    lowered = {n.lower() for n in names}
    for forbidden in FORBIDDEN_API_NAMES:
        assert forbidden not in lowered, f"forbidden API present: {forbidden}"
        assert not any(
            forbidden in n for n in lowered if "build" not in n and "validate" not in n
        ), f"forbidden fragment in API: {forbidden}"


def test_crash_contract_no_daemon_kill_symbols():
    """Studio process exit must not call daemon kill APIs — symbols absent."""
    pkg_root = REPO_ROOT / "scripts" / "atlas_studio"
    sources = [p.read_text(encoding="utf-8") for p in pkg_root.glob("*.py")]
    joined = "\n".join(sources)
    for sym in FORBIDDEN_CRASH_KILL_SYMBOLS:
        assert sym not in joined, f"crash-kill symbol present: {sym}"
    # AST: no calls named kill_*/terminate_* on daemon
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
                assert not label.startswith("terminate_agent")


# --- agent honesty ----------------------------------------------------------


def test_inactive_or_missing_agent_honest_not_crash():
    packet = build_injected(
        agent_id="missing-agent-xyz",
        control_view=injected_control_view(agent_status="NOT_REGISTERED"),
        telemetry_packet=injected_telemetry(agent_status="NOT_REGISTERED"),
    )
    assert packet["slice_status"] in ("DEGRADED", "UNKNOWN")
    assert packet["agent_status"] in (
        "NOT_REGISTERED",
        "UNKNOWN",
        "REGISTERED_INACTIVE",
        "DEGRADED",
    )
    errors = studio_snap.validate_studio_snapshot(packet)
    assert errors == []


def test_empty_injection_unknown_not_crash():
    packet = studio_snap.build_studio_snapshot(
        repository=REPO,
        agent_id="ghost",
        clock=clock,
    )
    assert packet["slice_status"] == "UNKNOWN"
    assert studio_snap.validate_studio_snapshot(packet) == []


# --- determinism ------------------------------------------------------------


def test_determinism_fingerprint_stable():
    a = build_injected()
    b = build_injected()
    assert a["snapshot_fingerprint"] == b["snapshot_fingerprint"]
    assert a["snapshot_fingerprint"] != "0" * 64


# --- programmatic builders (optional path) ----------------------------------


def test_programmatic_builders_path_uses_atlas_dag(monkeypatch):
    """When DAG inputs provided, call control_view/telemetry builders — not CLI."""
    import atlas_dag.control_view as cv_mod
    import atlas_dag.telemetry as tel_mod

    called = {"cv": 0, "tel": 0}

    real_cv = cv_mod.build_global_control_view
    real_tel = tel_mod.build_coordination_telemetry

    def wrap_cv(**kwargs):
        called["cv"] += 1
        return real_cv(**kwargs)

    def wrap_tel(**kwargs):
        called["tel"] += 1
        return real_tel(**kwargs)

    monkeypatch.setattr(cv_mod, "build_global_control_view", wrap_cv)
    monkeypatch.setattr(tel_mod, "build_coordination_telemetry", wrap_tel)

    snap = {
        "schema": "ATLAS_DAG_SNAPSHOT_V1",
        "nodes": [],
        "main_branch": "main",
        "safe_runnable_count": 0,
        "repository": REPO,
    }
    packet = studio_snap.build_studio_snapshot(
        repository=REPO,
        snapshot=snap,
        stacks={},
        events=[],
        clock=clock,
    )
    assert called["cv"] == 1
    assert called["tel"] == 1
    assert packet["panels"]["control_view"]["status"] == "OK"
    assert studio_snap.validate_studio_snapshot(packet) == []
