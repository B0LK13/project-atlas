"""Build ATLAS_STUDIO_SNAPSHOT_V1 from injected or live coordination truth.

STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
MODEL_PROVIDER != ATLAS_ARCHITECTURE
STUDIO_CRASH != AGENT_TASK_TERMINATION

Calls ``atlas_dag.control_view`` / ``telemetry`` / optional ``residuals``
programmatically. Never subprocesses ``atlas-dag`` CLI as protocol.
Never mutates DAG / vault / GitHub.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from atlas_studio import (
    ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
    GRANTS_NO_MUTATION,
    MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE,
    NO_CLI_TEXT_PARSING_AS_PROTOCOL,
    NO_WHOLESALE_CORE_REWRITE,
    REUSE_BEFORE_REIMPLEMENT,
    STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
)

SCHEMA_CONST = "ATLAS_STUDIO_SNAPSHOT_V1"
EVENT_SCHEMA_CONST = "ATLAS_STUDIO_EVENT_V1"
SCHEMA_FILE = "atlas_studio_snapshot_v1.schema.json"
EVENT_SCHEMA_FILE = "atlas_studio_event_v1.schema.json"

OK = "OK"
DEGRADED = "DEGRADED"
UNKNOWN = "UNKNOWN"

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


class StudioSnapshotError(RuntimeError):
    """Fail-closed Studio snapshot failure."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "no_cli_text_parsing_as_protocol": NO_CLI_TEXT_PARSING_AS_PROTOCOL,
        "atlas_daemon_is_authoritative_runtime": ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
        "studio_crash_ne_agent_task_termination": STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
        "model_provider_ne_atlas_architecture": MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE,
        "no_wholesale_core_rewrite": NO_WHOLESALE_CORE_REWRITE,
        "reuse_before_reimplement": REUSE_BEFORE_REIMPLEMENT,
    }


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(_load_schema(name), format_checker=FormatChecker())


def _honesty_false_paths(honesty: Any, *, prefix: str) -> list[str]:
    """Any honesty flag that is not strictly True is a contract failure."""
    if not isinstance(honesty, dict):
        return [f"{prefix}: honesty must be an object"]
    errors: list[str] = []
    for key, value in sorted(honesty.items()):
        if value is not True:
            errors.append(f"{prefix}/{key}: honesty flag must be true (got {value!r})")
    return errors


def _nested_packet_errors(
    body: dict | None,
    *,
    panel: str,
    expected_schema: str,
    validate_fn: Callable[[dict], list[str]] | None,
) -> list[str]:
    if body is None:
        return []
    if not isinstance(body, dict):
        return [f"panels/{panel}/body: must be an object"]
    errors: list[str] = []
    schema = body.get("schema")
    if schema != expected_schema:
        errors.append(
            f"panels/{panel}/body/schema: expected {expected_schema!r}, got {schema!r}"
        )
    errors.extend(_honesty_false_paths(body.get("honesty"), prefix=f"panels/{panel}/body/honesty"))
    if validate_fn is not None and schema == expected_schema:
        for err in validate_fn(body):
            errors.append(f"panels/{panel}/body: {err}")
    return errors


def validate_studio_snapshot(packet: dict) -> list[str]:
    """Validate outer Studio schema plus nested F15/F14 honesty/contracts."""
    validator = validator_for(SCHEMA_FILE)
    errors = [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]
    panels = packet.get("panels") if isinstance(packet, dict) else None
    if isinstance(panels, dict):
        cv_panel = panels.get("control_view")
        tel_panel = panels.get("telemetry")
        metrics_panel = panels.get("efficiency_metrics")
        if isinstance(cv_panel, dict):
            try:
                from atlas_dag.control_view import validate_control_view
            except ImportError:  # pragma: no cover - scripts path required
                validate_control_view = None  # type: ignore[assignment]
            errors.extend(
                _nested_packet_errors(
                    cv_panel.get("body"),
                    panel="control_view",
                    expected_schema="ATLAS_GLOBAL_CONTROL_VIEW_V1",
                    validate_fn=validate_control_view,
                )
            )
        if isinstance(tel_panel, dict):
            try:
                from atlas_dag.telemetry import validate_telemetry
            except ImportError:  # pragma: no cover
                validate_telemetry = None  # type: ignore[assignment]
            errors.extend(
                _nested_packet_errors(
                    tel_panel.get("body"),
                    panel="telemetry",
                    expected_schema="ATLAS_COORDINATION_TELEMETRY_V1",
                    validate_fn=validate_telemetry,
                )
            )
        if isinstance(metrics_panel, dict) and metrics_panel.get("body") is not None:
            body = metrics_panel.get("body")
            if isinstance(body, dict) and body.get("schema") == "ATLAS_EFFICIENCY_METRICS_V1":
                try:
                    from atlas_dag.telemetry import validate_metrics
                except ImportError:  # pragma: no cover
                    validate_metrics = None  # type: ignore[assignment]
                if validate_metrics is not None:
                    for err in validate_metrics(body):
                        errors.append(f"panels/efficiency_metrics/body: {err}")
                errors.extend(
                    _honesty_false_paths(
                        body.get("honesty"),
                        prefix="panels/efficiency_metrics/body/honesty",
                    )
                )
        # OK slice cannot wrap nested DEGRADED/UNKNOWN or invalid honesty.
        if packet.get("slice_status") == OK:
            for name in ("control_view", "telemetry", "efficiency_metrics", "residuals"):
                panel = panels.get(name)
                if isinstance(panel, dict) and panel.get("status") in (DEGRADED, UNKNOWN):
                    errors.append(
                        f"slice_status: cannot be OK while panels/{name}/status="
                        f"{panel.get('status')}"
                    )
    for ev in (packet.get("observation_events") or []) if isinstance(packet, dict) else []:
        if isinstance(ev, dict):
            errors.extend(
                f"observation_events: {e}" for e in validate_studio_event(ev)
            )
    return sorted(set(errors))


def _assess_nested_body(
    body: dict | None,
    *,
    expected_schema: str,
    validate_fn: Callable[[dict], list[str]],
) -> tuple[str, list[str]]:
    """Return panel status and notes for a nested coordination packet."""
    if body is None:
        return UNKNOWN, ["body_absent"]
    honesty_errs = _honesty_false_paths(body.get("honesty"), prefix="honesty")
    if honesty_errs:
        # Fail closed: dishonest nested packets must never present as OK.
        raise StudioSnapshotError(
            "nested honesty contract failed: " + "; ".join(honesty_errs)
        )
    if body.get("schema") != expected_schema:
        return DEGRADED, [f"unexpected_schema:{body.get('schema')!r}"]
    schema_errs = validate_fn(body)
    if schema_errs:
        return DEGRADED, [f"nested_schema:{e}" for e in schema_errs[:5]]
    return OK, []



def validate_studio_event(packet: dict) -> list[str]:
    validator = validator_for(EVENT_SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def make_observation_event(
    *,
    event_id: str,
    kind: str,
    clock: Callable[[], str],
    panel: str | None = None,
    message: str = "",
    payload: dict | None = None,
) -> dict:
    return {
        "schema": EVENT_SCHEMA_CONST,
        "event_id": event_id,
        "timestamp_utc": clock(),
        "kind": kind,
        "panel": panel,
        "message": message,
        "honesty": {
            "observation_ne_authority": True,
            "studio_ui_ne_authority": True,
            "grants_no_mutation": True,
        },
        "payload": dict(payload or {}),
    }


def _panel_wrap(status: str, body: dict | None = None, *,
                notes: list[str] | None = None) -> dict:
    out: dict[str, Any] = {
        "status": status,
        "notes": list(notes or []),
    }
    if body is not None:
        out["body"] = body
    return out


def _residuals_panel(residual_registry: dict | None) -> dict:
    if residual_registry is None:
        return _panel_wrap(UNKNOWN, notes=["residuals_not_provided"])
    residuals = residual_registry.get("residuals")
    if residuals is None and "schema" not in residual_registry:
        return _panel_wrap(DEGRADED, residual_registry,
                           notes=["residuals_shape_unexpected"])
    count = len(residuals) if isinstance(residuals, list) else None
    summary = {"residual_count": count} if count is not None else {}
    return _panel_wrap(
        OK,
        {"summary": summary, "registry": residual_registry},
        notes=["presentation_only"],
    )


def _derive_slice_status(
    *,
    control_view: dict | None,
    telemetry: dict | None,
    agent_status: str,
) -> str:
    if control_view is None and telemetry is None:
        return UNKNOWN
    if agent_status in ("REGISTRY_REQUIRED", "NOT_REGISTERED", "UNKNOWN"):
        return DEGRADED
    if agent_status in ("REGISTERED_INACTIVE",):
        return DEGRADED
    # Prefer control_view agent_status when present.
    cv_status = (control_view or {}).get("agent_status")
    if cv_status in ("REGISTERED_INACTIVE", "NOT_REGISTERED", "REGISTRY_REQUIRED"):
        return DEGRADED
    panels = (control_view or {}).get("panels") or {}
    if any((panels.get(k) or {}).get("status") == UNKNOWN for k in panels):
        return DEGRADED
    if control_view is None or telemetry is None:
        return DEGRADED
    return OK


def build_studio_snapshot(
    *,
    repository: str = "UNKNOWN",
    agent_id: str | None = None,
    control_view: dict | None = None,
    telemetry_packet: dict | None = None,
    efficiency_metrics: dict | None = None,
    residual_registry: dict | None = None,
    observation_events: list[dict] | None = None,
    snapshot: dict | None = None,
    stacks: dict | None = None,
    events: list[dict] | None = None,
    registry: Any = None,
    live: bool = False,
    repo: str | None = None,
    verifier_pool_path: Path | str | None = None,
    weights_path: Path | str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Build Studio RO snapshot.

    When ``control_view`` / ``telemetry_packet`` are injected (unit tests),
    they are used directly. Otherwise, when ``live=True`` or raw DAG inputs
    are provided, this function calls ``atlas_dag`` builders programmatically.
    """
    notes: list[str] = [
        "PRESENTATION_ONLY",
        "STUDIO_UI_NE_AUTHORITY",
        "NO_CLI_TEXT_PARSING_AS_PROTOCOL",
        "STUDIO_CRASH_NE_AGENT_TASK_TERMINATION",
    ]
    obs = list(observation_events or [])
    agent_status = "NONE"
    cv = control_view
    tel = telemetry_packet
    metrics = efficiency_metrics
    residuals = residual_registry

    if live and cv is None and tel is None:
        cv, tel, metrics, residuals, agent_status, live_notes = _build_live(
            agent_id=agent_id,
            repo=repo,
            verifier_pool_path=verifier_pool_path,
            weights_path=weights_path,
            clock=clock,
        )
        notes.extend(live_notes)
        repository = repo or repository
    elif cv is None and (snapshot is not None or stacks is not None or events is not None):
        cv, tel, metrics, residuals, agent_status = _build_from_dag_inputs(
            repository=repository,
            agent_id=agent_id,
            snapshot=snapshot,
            stacks=stacks,
            events=events,
            residual_registry=residuals,
            registry=registry,
            telemetry_packet=tel,
            verifier_pool_path=verifier_pool_path,
            clock=clock,
        )
    else:
        # Injected path: still may need metrics / residuals panels.
        if cv is not None:
            agent_status = str(cv.get("agent_status") or agent_status)
            repository = str(cv.get("repository") or repository)
        if tel is not None and metrics is None:
            from atlas_dag import telemetry as telemetry_mod

            metrics = telemetry_mod.build_efficiency_metrics(tel, clock=clock)
        if tel is not None and agent_status == "NONE":
            agent_status = str(tel.get("agent_status") or agent_status)
        if agent_id and agent_status in ("NONE", ""):
            # Missing registry / inactive: honest DEGRADED, never crash.
            agent_status = "UNKNOWN"

    if agent_id is not None and agent_status in ("NONE",):
        agent_status = "UNKNOWN"
        notes.append("agent_requested_but_status_unknown")
        obs.append(
            make_observation_event(
                event_id="studio-obs-agent-unknown",
                kind="SLICE_STATUS",
                clock=clock,
                panel="agents",
                message="agent inactive or missing → UNKNOWN/DEGRADED",
                payload={"agent_id": agent_id, "agent_status": agent_status},
            )
        )

    honesty = honesty_block()

    from atlas_dag.control_view import validate_control_view
    from atlas_dag.telemetry import validate_metrics, validate_telemetry

    cv_status, cv_notes = (UNKNOWN, ["control_view_unavailable"])
    tel_status, tel_notes = (UNKNOWN, ["telemetry_unavailable"])
    metrics_status, metrics_notes = (UNKNOWN, ["metrics_unavailable"])

    if cv is not None:
        cv_status, cv_notes = _assess_nested_body(
            cv,
            expected_schema="ATLAS_GLOBAL_CONTROL_VIEW_V1",
            validate_fn=validate_control_view,
        )
        cv_notes = ["reuse:atlas_dag.control_view", *cv_notes]
    if tel is not None:
        tel_status, tel_notes = _assess_nested_body(
            tel,
            expected_schema="ATLAS_COORDINATION_TELEMETRY_V1",
            validate_fn=validate_telemetry,
        )
        tel_notes = ["reuse:atlas_dag.telemetry", *tel_notes]
    if metrics is not None:
        if isinstance(metrics, dict) and metrics.get("schema") == "ATLAS_EFFICIENCY_METRICS_V1":
            metrics_status, metrics_notes = _assess_nested_body(
                metrics,
                expected_schema="ATLAS_EFFICIENCY_METRICS_V1",
                validate_fn=validate_metrics,
            )
            metrics_notes = [
                "reuse:atlas_dag.telemetry.build_efficiency_metrics",
                *metrics_notes,
            ]
        else:
            metrics_status, metrics_notes = DEGRADED, [
                "reuse:atlas_dag.telemetry.build_efficiency_metrics",
                "metrics_shape_unexpected",
            ]

    # Live path honesty: seal/evidence often absent by construction.
    if "live_mode" in notes:
        notes.append("LIVE_SEAL_SCAN=DEFERRED_OR_SKIPPED")
        notes.append("LIVE_EVIDENCE_STORE_MAY_BE_ABSENT")

    panels = {
        "control_view": _panel_wrap(cv_status, cv, notes=cv_notes),
        "telemetry": _panel_wrap(tel_status, tel, notes=tel_notes),
        "efficiency_metrics": _panel_wrap(metrics_status, metrics, notes=metrics_notes),
        "residuals": _residuals_panel(residuals),
    }

    slice_status = _derive_slice_status(
        control_view=cv, telemetry=tel, agent_status=agent_status,
    )
    if any(
        panels[name]["status"] in (DEGRADED, UNKNOWN)
        for name in ("control_view", "telemetry")
    ):
        if slice_status == OK:
            slice_status = DEGRADED
    if cv is None and tel is None:
        slice_status = UNKNOWN
        obs.append(
            make_observation_event(
                event_id="studio-obs-slice-unknown",
                kind="SLICE_STATUS",
                clock=clock,
                message="no control_view/telemetry available",
                payload={"slice_status": UNKNOWN},
            )
        )

    fp_body = {
        "honesty": honesty,
        "panels": {
            "control_view": (cv or {}).get("view_fingerprint") if cv else None,
            "telemetry": (tel or {}).get("telemetry_fingerprint") if tel else None,
            "residuals": (residuals or {}).get("registry_fingerprint")
            if isinstance(residuals, dict)
            else None,
            "efficiency": (metrics or {}).get("source_telemetry_fingerprint")
            if metrics
            else None,
            "panel_status": {k: v.get("status") for k, v in panels.items()},
        },
        "agent": agent_id,
        "agent_status": agent_status,
        "slice_status": slice_status,
        "repository": repository,
    }
    snapshot_fp = _canonical_sha256(fp_body)

    packet = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "repository": repository,
        "agent": agent_id,
        "agent_status": agent_status,
        "slice_status": slice_status,
        "snapshot_fingerprint": snapshot_fp,
        "honesty": honesty,
        "panels": panels,
        "observation_events": obs,
        "provenance": {
            "generator": "atlas-studio snapshot (AS-STUDIO-A0-001)",
            "presentation_only": True,
            "truth_sources": [
                "atlas_dag.control_view.build_global_control_view",
                "atlas_dag.telemetry.build_coordination_telemetry",
                "atlas_dag.telemetry.build_efficiency_metrics",
                "atlas_dag.residuals (optional)",
            ],
            "notes": notes,
            **honesty,
        },
    }
    return packet


def _build_from_dag_inputs(
    *,
    repository: str,
    agent_id: str | None,
    snapshot: dict | None,
    stacks: dict | None,
    events: list[dict] | None,
    residual_registry: dict | None,
    registry: Any,
    telemetry_packet: dict | None,
    verifier_pool_path: Path | str | None,
    clock: Callable[[], str],
) -> tuple[dict | None, dict | None, dict | None, dict | None, str]:
    from atlas_dag import control_view as control_view_mod
    from atlas_dag import telemetry as telemetry_mod

    residuals = residual_registry
    tel = telemetry_packet
    if tel is None:
        tel = telemetry_mod.build_coordination_telemetry(
            repository=repository,
            snapshot=snapshot,
            stacks=stacks,
            events=events or [],
            residual_registry=residuals,
            agent_id=agent_id,
            registry=registry,
            clock=clock,
            seal_projection="deferred_or_skipped",
        )
    cv = control_view_mod.build_global_control_view(
        repository=repository,
        snapshot=snapshot,
        stacks=stacks,
        events=events or [],
        residual_registry=residuals,
        telemetry_packet=tel,
        agent_id=agent_id,
        registry=registry,
        verifier_pool_path=verifier_pool_path,
        clock=clock,
        seal_scan="skipped_for_latency",
    )
    metrics = telemetry_mod.build_efficiency_metrics(tel, clock=clock)
    agent_status = str(cv.get("agent_status") or "UNKNOWN")
    return cv, tel, metrics, residuals, agent_status


def _build_live(
    *,
    agent_id: str | None,
    repo: str | None,
    verifier_pool_path: Path | str | None,
    weights_path: Path | str | None,
    clock: Callable[[], str],
) -> tuple[dict | None, dict | None, dict | None, dict | None, str, list[str]]:
    """Live path via GhClient — same builders as atlas-dag, no CLI parse."""
    notes: list[str] = ["live_mode"]
    try:
        from atlas_dag import agents as agents_mod
        from atlas_dag import control_view as control_view_mod
        from atlas_dag import events as events_mod
        from atlas_dag import frontier_matrix as frontier_matrix_mod
        from atlas_dag import residuals as residuals_mod
        from atlas_dag import score as score_mod
        from atlas_dag import stack as stack_mod
        from atlas_dag import steal as steal_mod
        from atlas_dag import telemetry as telemetry_mod
        from atlas_dag.gh import GhClient, GhError
        from atlas_dag.model import build_snapshot
    except ImportError as exc:
        notes.append(f"atlas_dag_import_failed:{exc}")
        return None, None, None, None, UNKNOWN, notes

    try:
        client = GhClient(repo=repo)
        snapshot = build_snapshot(client, pool_path=verifier_pool_path)
        registry = agents_mod.load_registry(None)
        stacks = stack_mod.build_stacks(
            snapshot["nodes"], client, snapshot.get("main_branch") or "main",
        )
        issue = client.dag_issue()
        events = (
            events_mod.ingest_comments(client.issue_comments(issue["number"])).events
            if issue
            else []
        )
        repository = client.repo or repo or "UNKNOWN"
        matrix = None
        residual_registry = None
        steal_plan = None
        if agent_id:
            residual_registry = residuals_mod.build_residual_registry(
                repository=repository,
                events=events,
                snapshot=snapshot,
                stacks=stacks,
                seal_by_pr=None,
                agent_id=agent_id,
                registry=registry,
            )
            weights, source = score_mod.load_weights(weights_path)
            matrix = frontier_matrix_mod.build_frontier_matrix(
                snapshot,
                agent_id=agent_id,
                registry=registry,
                stacks=stacks,
                weights=weights,
                weights_source=source,
                events=events,
                residual_registry=residual_registry,
                seal_by_pr=None,
            )
            steal_plan = steal_mod.plan_steal(
                snapshot,
                agent_id,
                registry,
                stacks=stacks,
                weights=weights,
                weights_source=source,
            )
        else:
            residual_registry = residuals_mod.build_residual_registry(
                repository=repository,
                events=events,
                snapshot=snapshot,
                stacks=stacks,
                seal_by_pr=None,
                agent_id=None,
                registry=registry,
            )
        tel = telemetry_mod.build_coordination_telemetry(
            repository=repository,
            snapshot=snapshot,
            stacks=stacks,
            events=events,
            matrix=matrix,
            residual_registry=residual_registry,
            steal_plan=steal_plan,
            agent_id=agent_id,
            registry=registry,
            clock=clock,
            seal_projection="deferred_or_skipped",
        )
        cv = control_view_mod.build_global_control_view(
            repository=repository,
            snapshot=snapshot,
            stacks=stacks,
            events=events,
            matrix=matrix,
            residual_registry=residual_registry,
            steal_plan=steal_plan,
            telemetry_packet=tel,
            agent_id=agent_id,
            registry=registry,
            verifier_pool_path=verifier_pool_path,
            clock=clock,
            seal_scan="skipped_for_latency",
        )
        metrics = telemetry_mod.build_efficiency_metrics(tel, clock=clock)
        agent_status = str(cv.get("agent_status") or "UNKNOWN")
        notes.append("seal_scan:skipped_for_latency")
        return cv, tel, metrics, residual_registry, agent_status, notes
    except GhError as exc:
        notes.append(f"gh_unavailable:{exc}")
        return None, None, None, None, UNKNOWN, notes
    except Exception as exc:  # noqa: BLE001 — live path must not crash Studio contract
        notes.append(f"live_degraded:{type(exc).__name__}:{exc}")
        return None, None, None, None, UNKNOWN, notes
