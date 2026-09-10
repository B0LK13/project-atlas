"""AS-STUDIO-A1-001 — read-only Mission Control projection.

STUDIO_UI != AUTHORITY
MISSION_CONTROL = PROJECTION_OF_ATLAS_TRUTH
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1
REUSE_BUILDERS != REIMPLEMENT_SEMANTICS

Builds ``ATLAS_STUDIO_MISSION_CONTROL_V1`` over A0 Studio snapshots plus F12
frontier matrix action-class / rankings when available. Never mutates DAG /
vault / GitHub. Never invents eligibility or ownership.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
    ATTENTION_NE_AUTHORIZATION,
    GRANTS_NO_MUTATION,
    NESTED_HONESTY_FAIL_CLOSED,
    NO_CLI_TEXT_PARSING_AS_PROTOCOL,
    O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME,
    O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN,
    REUSE_BEFORE_REIMPLEMENT,
    STALE_NE_CURRENT,
    STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
    UNKNOWN_NE_HEALTHY,
)
from atlas_studio.snapshot import (
    DEGRADED,
    OK,
    UNKNOWN,
    StudioSnapshotError,
    build_studio_snapshot,
    utcnow,
    validate_studio_snapshot,
    validator_for,
)

SCHEMA_CONST = "ATLAS_STUDIO_MISSION_CONTROL_V1"
SCHEMA_FILE = "atlas_studio_mission_control_v1.schema.json"

DEFAULT_MAX_AGE_SECONDS = 120

HEALTHY = "HEALTHY"
STALE = "STALE"
OFFLINE = "OFFLINE"
BLOCKED = "BLOCKED"
HUMAN_ATTENTION_REQUIRED = "HUMAN_ATTENTION_REQUIRED"

LIVE = "LIVE"

# Attention tiers (lower = higher urgency). Documented in build_attention docstring.
TIER_EXTERNAL_IV = 10
TIER_RESIDUAL_HUMAN = 20
TIER_HUMAN_GATE = 30
TIER_BLOCKED_HIGH_VALUE = 40
TIER_WAITING_CI_IV = 50
TIER_PANEL_DEGRADED = 60
TIER_AGENT = 70


class MissionControlError(StudioSnapshotError):
    """Fail-closed Mission Control failure (inherits A0 snapshot fail-closed)."""


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "no_cli_text_parsing_as_protocol": NO_CLI_TEXT_PARSING_AS_PROTOCOL,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "unknown_ne_healthy": UNKNOWN_NE_HEALTHY,
        "nested_honesty_fail_closed": NESTED_HONESTY_FAIL_CLOSED,
        "atlas_daemon_is_authoritative_runtime": ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
        "studio_crash_ne_agent_task_termination": STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
        "reuse_before_reimplement": REUSE_BEFORE_REIMPLEMENT,
        "o1_in_process_atlas_dag_ro_runtime": O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME,
        "o6_seal_evidence_may_be_unknown": O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN,
    }


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _parse_utc(ts: str) -> datetime | None:
    raw = (ts or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def compute_freshness(
    *,
    generated_at_utc: str,
    snapshot_fingerprint: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now_utc: str | None = None,
    offline: bool = False,
    unknown: bool = False,
) -> dict[str, Any]:
    """Compute freshness projection. STALE != CURRENT; no durable cache as truth."""
    notes: list[str] = ["rebuild_each_invocation", "no_durable_cache_as_truth"]
    if offline:
        return {
            "generated_at_utc": generated_at_utc,
            "snapshot_fingerprint": snapshot_fingerprint,
            "max_age_seconds": int(max_age_seconds),
            "age_seconds": None,
            "state": OFFLINE,
            "notes": [*notes, "live_gh_unavailable"],
        }
    if unknown:
        return {
            "generated_at_utc": generated_at_utc,
            "snapshot_fingerprint": snapshot_fingerprint,
            "max_age_seconds": int(max_age_seconds),
            "age_seconds": None,
            "state": UNKNOWN,
            "notes": [*notes, "freshness_unknown"],
        }
    generated = _parse_utc(generated_at_utc)
    now = _parse_utc(now_utc or generated_at_utc)
    if generated is None or now is None:
        return {
            "generated_at_utc": generated_at_utc,
            "snapshot_fingerprint": snapshot_fingerprint,
            "max_age_seconds": int(max_age_seconds),
            "age_seconds": None,
            "state": UNKNOWN,
            "notes": [*notes, "unparseable_timestamp"],
        }
    age = max(0.0, (now - generated).total_seconds())
    state = STALE if age > float(max_age_seconds) else LIVE
    if state == STALE:
        notes.append("age_exceeds_max_age_seconds")
    return {
        "generated_at_utc": generated_at_utc,
        "snapshot_fingerprint": snapshot_fingerprint,
        "max_age_seconds": int(max_age_seconds),
        "age_seconds": age,
        "state": state,
        "notes": notes,
    }


def _cv_panels(studio_snapshot: dict) -> dict:
    cv = ((studio_snapshot.get("panels") or {}).get("control_view") or {}).get("body")
    if not isinstance(cv, dict):
        return {}
    panels = cv.get("panels")
    return panels if isinstance(panels, dict) else {}


def _panel_status(panel: dict | None) -> str:
    if not isinstance(panel, dict):
        return UNKNOWN
    return str(panel.get("status") or UNKNOWN)


def _view_from_cv_panel(
    panels: dict,
    name: str,
    *,
    notes: list[str] | None = None,
) -> dict:
    panel = panels.get(name)
    status = _panel_status(panel if isinstance(panel, dict) else None)
    summary = None
    panel_notes: list[str] = []
    if isinstance(panel, dict):
        summary = panel.get("summary")
        panel_notes = list(panel.get("notes") or [])
    out_notes = ["projection_of_f15", *panel_notes, *(notes or [])]
    allowed = (OK, DEGRADED, UNKNOWN, BLOCKED, STALE, OFFLINE)
    return {
        "status": status if status in allowed else UNKNOWN,
        "notes": out_notes,
        "summary": summary,
        "source_panel": name,
        "references": [],
    }


def _agent_directory(registry: Any) -> dict[str, Any]:
    """Presentation-only agent id directory from registry (not authority)."""
    if registry is None:
        return {}
    raw = getattr(registry, "registry", None)
    if not isinstance(raw, dict):
        return {}
    agents = list(raw.get("agents") or [])
    active: list[str] = []
    inactive: list[str] = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        aid = str(agent.get("agent_id") or agent.get("id") or "").strip()
        if not aid:
            continue
        if agent.get("active", False):
            active.append(aid)
        else:
            inactive.append(aid)
    return {
        "active_agent_ids": sorted(set(active)),
        "inactive_agent_ids": sorted(set(inactive)),
    }


def _enrich_views_for_humans(
    views: dict,
    *,
    studio_snapshot: dict,
    registry: Any = None,
    agent_id: str | None = None,
    frontier_matrix: dict | None = None,
) -> dict:
    """Add discoverability fields so humans need not reconstruct from other tools."""
    out = dict(views)
    agents = dict(out.get("agents_lanes") or {})
    summary = dict(agents.get("summary") or {})
    directory = _agent_directory(registry)
    if directory:
        summary.update(directory)
    if agent_id is None and not frontier_matrix:
        summary["action_classes_hint"] = (
            "pass --agent <id> to unlock F12 action classes and rankings"
        )
    agents["summary"] = summary
    agents["notes"] = list(
        dict.fromkeys(
            [
                *(agents.get("notes") or []),
                "agent_directory_presentation_only",
            ]
        )
    )
    out["agents_lanes"] = agents

    # Efficiency metrics rollup into telemetry summary when present.
    metrics_panel = (studio_snapshot.get("panels") or {}).get("efficiency_metrics") or {}
    metrics_body = metrics_panel.get("body") if isinstance(metrics_panel, dict) else None
    if isinstance(metrics_body, dict):
        tel = dict(out.get("telemetry") or {})
        tsum = dict(tel.get("summary") or {})
        eff = metrics_body.get("summary")
        if isinstance(eff, dict):
            for key in (
                "waiting_human",
                "waiting_ci",
                "waiting_iv",
                "owned_lane_count",
                "unowned_lane_count",
                "open_residual_count",
            ):
                if key in eff:
                    tsum[key] = eff[key]
        tel["summary"] = tsum
        out["telemetry"] = tel

    # Residuals: prefer registry counts when A0 wrap only has residual_count.
    res = dict(out.get("residuals") or {})
    rsum = dict(res.get("summary") or {})
    res_body = (studio_snapshot.get("panels") or {}).get("residuals") or {}
    registry_body = None
    if isinstance(res_body, dict) and isinstance(res_body.get("body"), dict):
        registry_body = res_body["body"].get("registry")
    if isinstance(registry_body, dict):
        for key in ("open_count", "runnable_count", "blocked_count"):
            if registry_body.get(key) is not None:
                rsum[key] = registry_body.get(key)
        residuals = registry_body.get("residuals")
        if isinstance(residuals, list):
            open_ids = sorted(
                str(r.get("residual_id"))
                for r in residuals
                if isinstance(r, dict)
                and r.get("disposition") == "OPEN"
                and r.get("residual_id")
            )
            rsum["open_residual_ids"] = open_ids[:20]
            res["references"] = [
                {"kind": "residual_id", "id": rid} for rid in open_ids[:20]
            ]
    res["summary"] = rsum
    out["residuals"] = res
    return out


def _frontier_view(
    matrix: dict | None,
    cv_frontier: dict | None,
    *,
    expected_agent_id: str | None = None,
) -> dict:
    """Project F12 matrix action classes / rankings; UNKNOWN when matrix absent.

    Fail-closed agent binding (AS-STUDIO-A1 semantic boundary):
    when ``expected_agent_id`` is set and the injected matrix declares a
    different ``agent``, do **not** project that foreign frontier as OK for
    the requested agent. Status becomes DEGRADED, rankings/action_classes
    are cleared (None), and notes include ``AGENT_MATRIX_MISMATCH``.
    Foreign agent_id injection must not fabricate another agent's frontier.
    """
    cv_status = _panel_status(cv_frontier)
    cv_summary = (cv_frontier or {}).get("summary") if isinstance(cv_frontier, dict) else None
    if matrix is None or not isinstance(matrix, dict):
        return {
            "status": UNKNOWN,
            "notes": [
                "MATRIX_ABSENT",
                "action_classes_unknown_not_fake_healthy",
                "counts_only_f15_insufficient_for_action_class",
                "PRESENTATION_ONLY",
            ],
            "summary": cv_summary,
            "source_panel": "frontier",
            "action_classes": {
                "status": UNKNOWN,
                "by_action_class": None,
                "notes": ["MATRIX_ABSENT", "UNKNOWN_NE_HEALTHY"],
            },
            "rankings": {
                "status": UNKNOWN,
                "typed_rankings": None,
                "notes": ["MATRIX_ABSENT", "no_invented_eligibility"],
            },
            "human_gate_action_ids": [],
            "owner_decision_action_ids": [],
            "frontier_fingerprint": None,
            "references": [],
        }

    matrix_agent = str(matrix.get("agent") or "").strip()
    expected = (expected_agent_id or "").strip() or None
    if expected and matrix_agent and matrix_agent != expected:
        return {
            "status": DEGRADED,
            "notes": [
                "AGENT_MATRIX_MISMATCH",
                f"expected_agent={expected}",
                f"matrix_agent={matrix_agent}",
                "foreign_frontier_not_projected",
                "PRESENTATION_ONLY",
                "ACTION_RANK_NE_AUTHORITY",
            ],
            "summary": {
                **(cv_summary or {}),
                "eligible_count": None,
                "blocked_count": None,
                "ineligible_count": None,
                "action_count": None,
                "agent_matrix_mismatch": True,
            },
            "source_panel": "frontier",
            "action_classes": {
                "status": DEGRADED,
                "by_action_class": None,
                "notes": ["AGENT_MATRIX_MISMATCH", "foreign_frontier_suppressed"],
            },
            "rankings": {
                "status": DEGRADED,
                "typed_rankings": None,
                "notes": ["AGENT_MATRIX_MISMATCH", "no_fabricated_foreign_rankings"],
            },
            "human_gate_action_ids": [],
            "owner_decision_action_ids": [],
            "frontier_fingerprint": None,
            "references": [],
        }

    by_class = matrix.get("by_action_class") or {}
    rankings = matrix.get("typed_rankings") or {}
    human_gate_ids: list[str] = []
    owner_decision_ids: list[str] = []
    for action in matrix.get("actions") or []:
        if not isinstance(action, dict):
            continue
        aid = str(action.get("action_id") or "")
        if action.get("action_class") == "HUMAN_GATE":
            human_gate_ids.append(aid)
        if action.get("action_type") == "OWNER_DECISION":
            owner_decision_ids.append(aid)
    human_gate_ids = sorted(set(human_gate_ids))
    owner_decision_ids = sorted(set(owner_decision_ids))

    status = OK if matrix.get("frontier_fingerprint") else DEGRADED
    if cv_status in (DEGRADED, UNKNOWN) and status == OK:
        status = cv_status
    return {
        "status": status,
        "notes": [
            "reuse:atlas_dag.frontier_matrix.build_frontier_matrix",
            "PRESENTATION_ONLY",
            "ACTION_RANK_NE_AUTHORITY",
        ],
        "summary": {
            **(cv_summary or {}),
            "eligible_count": len(matrix.get("eligible_actions") or []),
            "blocked_count": len(matrix.get("blocked_actions") or []),
            "ineligible_count": len(matrix.get("ineligible_actions") or []),
            "action_count": len(matrix.get("actions") or []),
        },
        "source_panel": "frontier",
        "action_classes": {
            "status": OK,
            "by_action_class": dict(sorted(by_class.items())),
            "notes": ["from_f12_by_action_class"],
        },
        "rankings": {
            "status": OK,
            "typed_rankings": dict(sorted(rankings.items())),
            "notes": ["from_f12_typed_rankings", "no_studio_re_rank"],
        },
        "human_gate_action_ids": human_gate_ids,
        "owner_decision_action_ids": owner_decision_ids,
        "frontier_fingerprint": matrix.get("frontier_fingerprint"),
        "references": [
            {"kind": "frontier_fingerprint", "id": matrix.get("frontier_fingerprint")}
        ],
    }


def _human_gates_view(frontier_view: dict, panels: dict) -> dict:
    ids = list(frontier_view.get("human_gate_action_ids") or [])
    owner_ids = list(frontier_view.get("owner_decision_action_ids") or [])
    honesty = panels.get("system_honesty") if isinstance(panels.get("system_honesty"), dict) else {}
    ext_iv = bool((honesty.get("summary") or {}).get("external_iv_gated"))
    notes = ["ATTENTION_NE_AUTHORIZATION", "PRESENTATION_ONLY"]
    status = OK
    if ids or owner_ids or ext_iv:
        status = BLOCKED if (ids or owner_ids) else DEGRADED
        if ids:
            notes.append("HUMAN_GATE_ACTIONS_PRESENT")
        if owner_ids:
            notes.append("OWNER_DECISION_ACTIONS_PRESENT")
        if ext_iv:
            notes.append("EXTERNAL_IV_GATED")
    if frontier_view.get("status") == UNKNOWN and not ids and not owner_ids:
        return {
            "status": UNKNOWN,
            "notes": [*notes, "MATRIX_ABSENT_HUMAN_GATES_UNKNOWN"],
            "summary": {
                "human_gate_count": None,
                "owner_decision_count": None,
                "external_iv_gated": ext_iv,
            },
            "source_panel": "frontier+system_honesty",
            "references": [],
        }
    return {
        "status": status,
        "notes": notes,
        "summary": {
            "human_gate_count": len(ids),
            "owner_decision_count": len(owner_ids),
            "external_iv_gated": ext_iv,
            "human_gate_action_ids": ids,
            "owner_decision_action_ids": owner_ids,
        },
        "source_panel": "frontier+system_honesty",
        "references": [{"kind": "action_id", "id": i} for i in ids[:20]],
    }


def build_attention(
    *,
    studio_snapshot: dict,
    views: dict,
    frontier_matrix: dict | None,
) -> list[dict]:
    """Deterministic human-attention ranking (ATTENTION != AUTHORIZATION).

    Sort key (ascending urgency, then stable id)::

        (tier, -secondary, kind, attention_id)

    Tiers (lower = more urgent):
      10 EXTERNAL_IV_GATED — system_honesty.external_iv_gated
      20 residuals needing human — OPEN + OWNER_DECISION / OWNER_DECISION_REQUIRES_HUMAN
      30 HUMAN_GATE / OWNER_DECISION actions from F12 matrix (when present)
      40 blocked high-value — matrix typed_rankings.highest_value_blocker_removal
      50 waiting_ci / waiting_iv — dispatch_gates summary
      60 DEGRADED / UNKNOWN Mission Control views (except attention itself)
      70 agent inactive / not registered / registry required

    Never invents eligibility: matrix-derived items appear only when matrix is
    injected/built. Absent matrix does not fabricate empty healthy ranks.
    """
    items: list[dict] = []
    panels = _cv_panels(studio_snapshot)

    honesty_panel = panels.get("system_honesty") if isinstance(panels, dict) else None
    if isinstance(honesty_panel, dict):
        summary = honesty_panel.get("summary") or {}
        if summary.get("external_iv_gated") or "EXTERNAL_IV_GATED" in (
            honesty_panel.get("notes") or []
        ):
            items.append(
                {
                    "attention_id": "external-iv-gated",
                    "kind": "EXTERNAL_IV_GATED",
                    "tier": TIER_EXTERNAL_IV,
                    "title": "External IV gated / unbound",
                    "detail": "Verifier pool unbound or absent (EXTERNAL_IV_GATED).",
                    "references": [],
                    "attention_ne_authorization": True,
                    "_secondary": 0,
                }
            )

    residuals_body = (
        ((studio_snapshot.get("panels") or {}).get("residuals") or {}).get("body") or {}
    )
    registry = residuals_body.get("registry") if isinstance(residuals_body, dict) else None
    if isinstance(registry, dict):
        for rec in registry.get("residuals") or []:
            if not isinstance(rec, dict):
                continue
            if rec.get("disposition") != "OPEN":
                continue
            reasons = [str(r) for r in (rec.get("blocking_reasons") or [])]
            needs_human = (
                rec.get("required_action_type") == "OWNER_DECISION"
                or any("OWNER_DECISION" in r or "HUMAN" in r for r in reasons)
            )
            if not needs_human:
                continue
            rid = str(rec.get("residual_id") or "unknown")
            items.append(
                {
                    "attention_id": f"residual:{rid}",
                    "kind": "RESIDUAL_HUMAN",
                    "tier": TIER_RESIDUAL_HUMAN,
                    "title": f"Residual needs human: {rid}",
                    "detail": "; ".join(reasons) or "OWNER_DECISION",
                    "references": [{"kind": "residual_id", "id": rid}],
                    "attention_ne_authorization": True,
                    "_secondary": 0,
                }
            )

    if isinstance(frontier_matrix, dict):
        for action in frontier_matrix.get("actions") or []:
            if not isinstance(action, dict):
                continue
            aid = str(action.get("action_id") or "")
            aclass = action.get("action_class")
            atype = action.get("action_type")
            if aclass == "HUMAN_GATE" or atype == "OWNER_DECISION":
                items.append(
                    {
                        "attention_id": f"matrix-gate:{aid}",
                        "kind": "HUMAN_GATE" if aclass == "HUMAN_GATE" else "OWNER_DECISION",
                        "tier": TIER_HUMAN_GATE,
                        "title": f"Human gate action: {aid}",
                        "detail": f"state={action.get('runnable_state')}",
                        "references": [{"kind": "action_id", "id": aid}],
                        "attention_ne_authorization": True,
                        "_secondary": int(action.get("pr") or 0),
                    }
                )
        rankings = frontier_matrix.get("typed_rankings") or {}
        for aid in rankings.get("highest_value_blocker_removal") or []:
            items.append(
                {
                    "attention_id": f"blocked-hv:{aid}",
                    "kind": "BLOCKED_HIGH_VALUE",
                    "tier": TIER_BLOCKED_HIGH_VALUE,
                    "title": f"Blocked high-value: {aid}",
                    "detail": "from F12 typed_rankings.highest_value_blocker_removal",
                    "references": [{"kind": "action_id", "id": str(aid)}],
                    "attention_ne_authorization": True,
                    "_secondary": 0,
                }
            )

    dg = panels.get("dispatch_gates") if isinstance(panels, dict) else None
    if isinstance(dg, dict):
        summary = dg.get("summary") or {}
        waiting_ci = int(summary.get("waiting_ci") or 0)
        waiting_iv = int(summary.get("waiting_iv") or 0)
        if waiting_ci:
            items.append(
                {
                    "attention_id": "waiting-ci",
                    "kind": "WAITING_CI",
                    "tier": TIER_WAITING_CI_IV,
                    "title": f"Waiting on CI ({waiting_ci})",
                    "detail": "dispatch_gates.waiting_ci",
                    "references": [],
                    "attention_ne_authorization": True,
                    "_secondary": waiting_ci,
                }
            )
        if waiting_iv:
            items.append(
                {
                    "attention_id": "waiting-iv",
                    "kind": "WAITING_IV",
                    "tier": TIER_WAITING_CI_IV,
                    "title": f"Waiting on IV ({waiting_iv})",
                    "detail": "dispatch_gates.waiting_iv",
                    "references": [],
                    "attention_ne_authorization": True,
                    "_secondary": waiting_iv,
                }
            )

    for name, view in sorted(views.items()):
        if name == "attention":
            continue
        if not isinstance(view, dict):
            continue
        status = view.get("status")
        if status in (DEGRADED, UNKNOWN, BLOCKED, OFFLINE, STALE):
            items.append(
                {
                    "attention_id": f"view:{name}:{status}",
                    "kind": "PANEL_STATUS",
                    "tier": TIER_PANEL_DEGRADED,
                    "title": f"View {name} is {status}",
                    "detail": "; ".join(view.get("notes") or [])[:200],
                    "references": [{"kind": "view", "id": name}],
                    "attention_ne_authorization": True,
                    "_secondary": 0,
                }
            )

    agent_status = str(studio_snapshot.get("agent_status") or "")
    if agent_status in (
        "NOT_REGISTERED",
        "REGISTERED_INACTIVE",
        "REGISTRY_REQUIRED",
        "UNKNOWN",
    ):
        items.append(
            {
                "attention_id": f"agent:{agent_status}",
                "kind": "AGENT_STATUS",
                "tier": TIER_AGENT,
                "title": f"Agent status {agent_status}",
                "detail": "Inactive/missing agent → honest DEGRADED/UNKNOWN",
                "references": [],
                "attention_ne_authorization": True,
                "_secondary": 0,
            }
        )

    by_id: dict[str, dict] = {}
    for item in items:
        aid = item["attention_id"]
        if aid not in by_id:
            by_id[aid] = item
    ranked = sorted(
        by_id.values(),
        key=lambda it: (
            int(it["tier"]),
            -int(it.get("_secondary") or 0),
            str(it["kind"]),
            str(it["attention_id"]),
        ),
    )
    out: list[dict] = []
    for item in ranked:
        clean = {k: v for k, v in item.items() if not k.startswith("_")}
        clean["attention_ne_authorization"] = True
        out.append(clean)
    return out


def _derive_mission_status(
    *,
    slice_status: str,
    freshness: dict,
    views: dict,
    attention: list[dict],
) -> str:
    """Derive badge. UNKNOWN seal/evidence must never promote to HEALTHY (O6)."""
    fres_state = freshness.get("state")
    if fres_state == OFFLINE:
        return OFFLINE
    if fres_state == STALE:
        return STALE
    if fres_state == UNKNOWN and slice_status == UNKNOWN:
        return UNKNOWN

    seal = views.get("postmerge_seal") or {}
    evidence = views.get("evidence") or {}
    seal_unknown = seal.get("status") == UNKNOWN
    evidence_unknown = evidence.get("status") == UNKNOWN

    high_attention = any(
        int(a.get("tier") or 99) <= TIER_HUMAN_GATE for a in attention
    )
    if high_attention:
        return HUMAN_ATTENTION_REQUIRED

    if (views.get("frontier") or {}).get("status") == BLOCKED:
        return BLOCKED
    if (views.get("human_gates") or {}).get("status") == BLOCKED:
        return BLOCKED

    if slice_status == UNKNOWN:
        return UNKNOWN
    if slice_status == DEGRADED:
        return DEGRADED

    # O6: UNKNOWN seal/evidence must not silently read as HEALTHY.
    if seal_unknown or evidence_unknown:
        return DEGRADED

    if fres_state == LIVE and slice_status == OK:
        return HEALTHY
    return DEGRADED


_ATTENTION_AUTH_FALSE_KEYS = (
    "authorized",
    "permitted",
    "executable",
    "authorization_granted",
    "mutation_authorized",
)


def validate_mission_control(packet: dict) -> list[str]:
    """Validate MC schema + embedded A0 snapshot nested honesty fail-closed."""
    validator = validator_for(SCHEMA_FILE)
    errors = [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]
    if not isinstance(packet, dict):
        return sorted(set(errors)) or ["<root>: must be object"]

    honesty = packet.get("honesty")
    if isinstance(honesty, dict):
        for key, value in sorted(honesty.items()):
            if value is not True:
                errors.append(f"honesty/{key}: must be true (got {value!r})")

    snap = packet.get("studio_snapshot")
    if isinstance(snap, dict):
        errors.extend(
            f"studio_snapshot: {e}" for e in validate_studio_snapshot(snap)
        )
        if packet.get("mission_status") == HEALTHY or packet.get("slice_status") == OK:
            for name in ("control_view", "telemetry"):
                panel = (snap.get("panels") or {}).get(name) or {}
                body = panel.get("body") if isinstance(panel, dict) else None
                if isinstance(body, dict):
                    for hk, hv in (body.get("honesty") or {}).items():
                        if hv is not True:
                            errors.append(
                                f"mission_status/slice_status: nested "
                                f"{name} honesty/{hk}={hv!r} refuse OK/HEALTHY"
                            )

    views = packet.get("views")
    if isinstance(views, dict):
        for name, view in views.items():
            if not isinstance(view, dict) or not view:
                errors.append(f"views/{name}: empty or non-object panel")
            elif "status" not in view or "notes" not in view:
                errors.append(f"views/{name}: status+notes required")

    attention = packet.get("attention")
    if isinstance(attention, list):
        for idx, item in enumerate(attention):
            if not isinstance(item, dict):
                errors.append(f"attention/{idx}: must be object")
                continue
            if item.get("attention_ne_authorization") is not True:
                errors.append(
                    f"attention/{idx}: attention_ne_authorization must be true"
                )
            for key in _ATTENTION_AUTH_FALSE_KEYS:
                if item.get(key) is True:
                    errors.append(
                        f"attention/{idx}: {key}=true refused "
                        f"(ATTENTION_NE_AUTHORIZATION)"
                    )

    if packet.get("mission_status") == HEALTHY and isinstance(views, dict):
        for name in ("postmerge_seal", "evidence"):
            if (views.get(name) or {}).get("status") == UNKNOWN:
                errors.append(
                    f"mission_status: cannot be HEALTHY while views/{name}=UNKNOWN"
                )
        frontier = views.get("frontier") or {}
        if "AGENT_MATRIX_MISMATCH" in (frontier.get("notes") or []):
            errors.append(
                "mission_status: cannot be HEALTHY under AGENT_MATRIX_MISMATCH"
            )

    if packet.get("mission_status") == HEALTHY and (
        (packet.get("freshness") or {}).get("state") != LIVE
    ):
        errors.append("mission_status: HEALTHY requires freshness.state=LIVE")

    return sorted(set(errors))


def _effective_frontier_matrix(
    matrix: dict | None,
    *,
    expected_agent_id: str | None,
) -> dict | None:
    """Drop foreign-agent matrices so attention cannot invent another frontier."""
    if matrix is None or not isinstance(matrix, dict):
        return None
    expected = (expected_agent_id or "").strip() or None
    matrix_agent = str(matrix.get("agent") or "").strip()
    if expected and matrix_agent and matrix_agent != expected:
        return None
    return matrix


def _build_views(
    *,
    studio_snapshot: dict,
    frontier_matrix: dict | None,
    expected_agent_id: str | None = None,
) -> dict:
    panels = _cv_panels(studio_snapshot)
    frontier = _frontier_view(
        frontier_matrix,
        panels.get("frontier"),
        expected_agent_id=expected_agent_id,
    )
    human_gates = _human_gates_view(frontier, panels)

    tel_panel = (studio_snapshot.get("panels") or {}).get("telemetry") or {}
    metrics_panel = (studio_snapshot.get("panels") or {}).get("efficiency_metrics") or {}
    residuals_panel = (studio_snapshot.get("panels") or {}).get("residuals") or {}

    health_notes = [
        f"slice_status={studio_snapshot.get('slice_status')}",
        "STUDIO_UI_NE_AUTHORITY",
    ]
    health_status = studio_snapshot.get("slice_status") or UNKNOWN
    return {
        "health": {
            "status": health_status if health_status in (OK, DEGRADED, UNKNOWN) else UNKNOWN,
            "notes": health_notes,
            "summary": {
                "slice_status": studio_snapshot.get("slice_status"),
                "agent_status": studio_snapshot.get("agent_status"),
                "a0_fingerprint": studio_snapshot.get("snapshot_fingerprint"),
            },
            "source_panel": None,
            "references": [],
        },
        "agents_lanes": _view_from_cv_panel(panels, "agents"),
        "ownership": _view_from_cv_panel(panels, "ownership"),
        "frontier": frontier,
        "human_gates": human_gates,
        "residuals": {
            "status": residuals_panel.get("status") or UNKNOWN,
            "notes": ["projection_of_a0_residuals", *(residuals_panel.get("notes") or [])],
            "summary": (
                (residuals_panel.get("body") or {}).get("summary")
                if isinstance(residuals_panel.get("body"), dict)
                else None
            ),
            "source_panel": "residuals",
            "references": [],
        },
        "ci_iv": _view_from_cv_panel(panels, "dispatch_gates", notes=["ci_iv_projection"]),
        "telemetry": {
            "status": tel_panel.get("status") or UNKNOWN,
            "notes": [
                "TELEMETRY_NE_AUTHORITY",
                *(tel_panel.get("notes") or []),
                *(metrics_panel.get("notes") or []),
            ],
            "summary": {
                "telemetry_status": tel_panel.get("status"),
                "metrics_status": metrics_panel.get("status"),
            },
            "source_panel": "telemetry",
            "references": [],
        },
        "stacks": _view_from_cv_panel(panels, "stacks"),
        "postmerge_seal": _view_from_cv_panel(
            panels, "postmerge", notes=["O6_seal_may_be_unknown", "UNKNOWN_NE_HEALTHY"]
        ),
        "evidence": _view_from_cv_panel(
            panels,
            "evidence_health",
            notes=["O6_evidence_may_be_unknown", "UNKNOWN_NE_HEALTHY"],
        ),
        "attention": {
            "status": OK,
            "notes": ["ATTENTION_NE_AUTHORIZATION", "deterministic_ranking"],
            "summary": {"count": 0},
            "source_panel": None,
            "references": [],
        },
    }


def build_mission_control(
    *,
    repository: str = "UNKNOWN",
    agent_id: str | None = None,
    studio_snapshot: dict | None = None,
    control_view: dict | None = None,
    telemetry_packet: dict | None = None,
    efficiency_metrics: dict | None = None,
    residual_registry: dict | None = None,
    frontier_matrix: dict | None = None,
    snapshot: dict | None = None,
    stacks: dict | None = None,
    events: list[dict] | None = None,
    registry: Any = None,
    live: bool = False,
    live_client: Any = None,
    repo: str | None = None,
    verifier_pool_path: Path | str | None = None,
    weights_path: Path | str | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    clock: Callable[[], str] = utcnow,
    now_clock: Callable[[], str] | None = None,
) -> dict:
    """Build ATLAS_STUDIO_MISSION_CONTROL_V1.

    Injection paths (unit tests):
      - ``studio_snapshot`` (+ optional ``frontier_matrix``)
      - or ``control_view`` / ``telemetry_packet`` / residuals / matrix

    Live path (O1): same in-process ``atlas_dag`` builders as A0 — including
    ``build_frontier_matrix`` when agent context allows — no atlasd required.
    Rebuilds on every invocation; prior frames are never treated as LIVE without
    rebuild.
    """
    notes: list[str] = [
        "PRESENTATION_ONLY",
        "MISSION_CONTROL_PROJECTION",
        "ATTENTION_NE_AUTHORIZATION",
        "STALE_NE_CURRENT",
        "UNKNOWN_NE_HEALTHY",
        "NO_MUTATION_API_IN_A1",
        "O1_IN_PROCESS_ATLAS_DAG",
        "O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN",
    ]
    offline = False
    matrix = frontier_matrix
    snap = studio_snapshot

    if live and snap is None and control_view is None:
        snap, matrix, offline, live_notes, live_registry = _build_live_mc(
            agent_id=agent_id,
            repo=repo,
            verifier_pool_path=verifier_pool_path,
            weights_path=weights_path,
            clock=clock,
            live_client=live_client,
        )
        notes.extend(live_notes)
        repository = (snap or {}).get("repository") or repo or repository
        if registry is None:
            registry = live_registry
    elif snap is None:
        snap = build_studio_snapshot(
            repository=repository,
            agent_id=agent_id,
            control_view=control_view,
            telemetry_packet=telemetry_packet,
            efficiency_metrics=efficiency_metrics,
            residual_registry=residual_registry,
            snapshot=snapshot,
            stacks=stacks,
            events=events,
            registry=registry,
            live=False,
            repo=repo,
            verifier_pool_path=verifier_pool_path,
            weights_path=weights_path,
            clock=clock,
        )
        if matrix is None and snapshot is not None and agent_id and registry is not None:
            matrix = _try_build_matrix(
                snapshot=snapshot,
                agent_id=agent_id,
                registry=registry,
                stacks=stacks,
                events=events,
                residual_registry=residual_registry,
                weights_path=weights_path,
                clock=clock,
            )
            if matrix is not None:
                notes.append("reuse:build_frontier_matrix")

    assert snap is not None
    snap_errors = validate_studio_snapshot(snap)
    if snap_errors:
        bad_honesty = [e for e in snap_errors if "honesty" in e]
        if bad_honesty:
            raise MissionControlError(
                "nested honesty contract failed: " + "; ".join(bad_honesty[:5])
            )

    repository = str(snap.get("repository") or repository)
    agent_status = str(snap.get("agent_status") or "UNKNOWN")
    slice_status = str(snap.get("slice_status") or UNKNOWN)
    bound_agent = agent_id if agent_id is not None else snap.get("agent")
    if isinstance(bound_agent, str):
        bound_agent = bound_agent.strip() or None
    else:
        bound_agent = None
    # Suppress foreign-agent matrix for attention (fail-closed; views also degrade).
    attention_matrix = _effective_frontier_matrix(
        matrix, expected_agent_id=bound_agent
    )
    if (
        isinstance(matrix, dict)
        and attention_matrix is None
        and bound_agent
        and str(matrix.get("agent") or "").strip()
        and str(matrix.get("agent") or "").strip() != bound_agent
    ):
        notes.append("AGENT_MATRIX_MISMATCH")
        notes.append("foreign_frontier_suppressed")

    views = _build_views(
        studio_snapshot=snap,
        frontier_matrix=matrix,
        expected_agent_id=bound_agent,
    )
    views = _enrich_views_for_humans(
        views,
        studio_snapshot=snap,
        registry=registry,
        agent_id=bound_agent,
        frontier_matrix=attention_matrix,
    )
    attention = build_attention(
        studio_snapshot=snap, views=views, frontier_matrix=attention_matrix
    )
    views["attention"] = {
        "status": OK,
        "notes": ["ATTENTION_NE_AUTHORIZATION", "deterministic_ranking"],
        "summary": {"count": len(attention)},
        "source_panel": None,
        "references": [
            {"kind": "attention_id", "id": a["attention_id"]} for a in attention[:20]
        ],
    }

    honesty = honesty_block()
    generated_at = clock()
    fp_body = {
        "honesty": honesty,
        "slice_status": slice_status,
        "a0_fingerprint": snap.get("snapshot_fingerprint"),
        "frontier_fingerprint": (
            (attention_matrix or {}).get("frontier_fingerprint")
            if isinstance(attention_matrix, dict)
            else None
        ),
        "views_status": {k: v.get("status") for k, v in sorted(views.items())},
        "attention_ids": [a["attention_id"] for a in attention],
        "agent": bound_agent,
        "repository": repository,
        "agent_matrix_mismatch": "AGENT_MATRIX_MISMATCH" in notes,
    }
    snapshot_fp = _canonical_sha256(fp_body)

    now_ts = (now_clock or clock)()
    freshness = compute_freshness(
        generated_at_utc=generated_at,
        snapshot_fingerprint=snapshot_fp,
        max_age_seconds=max_age_seconds,
        now_utc=now_ts,
        offline=offline,
    )

    mission_status = _derive_mission_status(
        slice_status=slice_status,
        freshness=freshness,
        views=views,
        attention=attention,
    )

    return {
        "schema": SCHEMA_CONST,
        "generated_at_utc": generated_at,
        "repository": repository,
        "agent": bound_agent,
        "agent_status": agent_status,
        "slice_status": slice_status,
        "mission_status": mission_status,
        "snapshot_fingerprint": snapshot_fp,
        "freshness": freshness,
        "honesty": honesty,
        "views": views,
        "attention": attention,
        "studio_snapshot": snap,
        "observation_events": list(snap.get("observation_events") or []),
        "provenance": {
            "generator": "atlas-studio mission-control (AS-STUDIO-A1-001)",
            "presentation_only": True,
            "truth_sources": [
                "atlas_studio.snapshot.build_studio_snapshot",
                "atlas_dag.control_view.build_global_control_view",
                "atlas_dag.telemetry.build_coordination_telemetry",
                "atlas_dag.telemetry.build_efficiency_metrics",
                "atlas_dag.residuals.build_residual_registry",
                "atlas_dag.frontier_matrix.build_frontier_matrix",
            ],
            "notes": notes,
            **honesty,
        },
    }


def _try_build_matrix(
    *,
    snapshot: dict,
    agent_id: str,
    registry: Any,
    stacks: dict | None,
    events: list[dict] | None,
    residual_registry: dict | None,
    weights_path: Path | str | None,
    clock: Callable[[], str],
) -> dict | None:
    try:
        from atlas_dag import frontier_matrix as frontier_matrix_mod
        from atlas_dag import score as score_mod
    except ImportError:
        return None
    try:
        weights, source = score_mod.load_weights(weights_path)
        return frontier_matrix_mod.build_frontier_matrix(
            snapshot,
            agent_id=agent_id,
            registry=registry,
            stacks=stacks,
            weights=weights,
            weights_source=source,
            events=events or [],
            residual_registry=residual_registry,
            seal_by_pr=None,
            clock=clock,
        )
    except Exception:  # noqa: BLE001 — projection must degrade, not crash
        return None


def _build_live_mc(
    *,
    agent_id: str | None,
    repo: str | None,
    verifier_pool_path: Path | str | None,
    weights_path: Path | str | None,
    clock: Callable[[], str],
    live_client: Any = None,
) -> tuple[dict, dict | None, bool, list[str], Any]:
    """Live RO path via GhClient + atlas_dag builders (O1).

    Returns ``(snapshot, matrix, offline, notes, registry)``.
    """
    notes: list[str] = ["live_mode", "o1_in_process_atlas_dag"]
    registry: Any = None
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
        snap = build_studio_snapshot(
            repository=repo or "UNKNOWN",
            agent_id=agent_id,
            clock=clock,
        )
        return snap, None, False, notes, None

    try:
        client = live_client if live_client is not None else GhClient(repo=repo)
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
        residual_registry = residuals_mod.build_residual_registry(
            repository=repository,
            events=events,
            snapshot=snapshot,
            stacks=stacks,
            seal_by_pr=None,
            agent_id=agent_id,
            registry=registry,
        )
        steal_plan = None
        if agent_id:
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
                clock=clock,
            )
            steal_plan = steal_mod.plan_steal(
                snapshot,
                agent_id,
                registry,
                stacks=stacks,
                weights=weights,
                weights_source=source,
            )
            notes.append("reuse:build_frontier_matrix")
        else:
            notes.append("matrix_skipped_no_agent")

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
        snap = build_studio_snapshot(
            repository=repository,
            agent_id=agent_id,
            control_view=cv,
            telemetry_packet=tel,
            efficiency_metrics=metrics,
            residual_registry=residual_registry,
            clock=clock,
        )
        notes.append("seal_scan:skipped_for_latency")
        notes.append("LIVE_SEAL_SCAN=DEFERRED_OR_SKIPPED")
        notes.append("LIVE_EVIDENCE_STORE_MAY_BE_ABSENT")
        return snap, matrix, False, notes, registry
    except GhError as exc:
        notes.append(f"gh_unavailable:{exc}")
        snap = build_studio_snapshot(
            repository=repo or "UNKNOWN",
            agent_id=agent_id,
            clock=clock,
        )
        return snap, None, True, notes, registry
    except Exception as exc:  # noqa: BLE001
        notes.append(f"live_degraded:{type(exc).__name__}:{exc}")
        snap = build_studio_snapshot(
            repository=repo or "UNKNOWN",
            agent_id=agent_id,
            clock=clock,
        )
        return snap, None, False, notes, registry


def format_mission_control_tui(packet: dict) -> str:
    """Human-readable Mission Control sections with status badges."""
    lines: list[str] = []
    ms = packet.get("mission_status", UNKNOWN)
    fres = packet.get("freshness") or {}
    lines.append(
        f"MISSION CONTROL  status={ms}  freshness={fres.get('state')}  "
        f"slice={packet.get('slice_status')}  repo={packet.get('repository')}"
    )
    lines.append(
        f"agent={packet.get('agent')}  agent_status={packet.get('agent_status')}  "
        f"fp={(packet.get('snapshot_fingerprint') or '')[:12]}…  "
        f"age={fres.get('age_seconds')}s  max_age={fres.get('max_age_seconds')}s"
    )
    lines.append(
        "HONESTY: STUDIO_UI!=AUTHORITY · ATTENTION!=AUTHORIZATION · "
        "STALE!=CURRENT · UNKNOWN!=HEALTHY · NO_MUTATION"
    )
    lines.append("")

    attention = packet.get("attention") or []
    lines.append("=== WHAT MATTERS NEXT (attention ≠ authorization) ===")
    if not attention:
        lines.append("  (none)")
    else:
        for item in attention[:5]:
            lines.append(
                f"  tier={item.get('tier'):<3} [{item.get('kind')}] {item.get('title')}"
            )
        if len(attention) > 5:
            lines.append(f"  … +{len(attention) - 5} more (see ATTENTION)")
    lines.append("")

    agents_view = (packet.get("views") or {}).get("agents_lanes") or {}
    agents_sum = agents_view.get("summary") if isinstance(agents_view, dict) else None
    if isinstance(agents_sum, dict):
        active_ids = agents_sum.get("active_agent_ids") or []
        inactive_ids = agents_sum.get("inactive_agent_ids") or []
        lines.append("=== AGENTS ===")
        lines.append(
            f"  active={agents_sum.get('active_count')}  "
            f"inactive={agents_sum.get('inactive_count')}  "
            f"total={agents_sum.get('total_count')}"
        )
        if active_ids:
            lines.append(f"  active_ids: {', '.join(active_ids)}")
        if inactive_ids:
            lines.append(f"  inactive_ids: {', '.join(inactive_ids[:8])}")
        hint = agents_sum.get("action_classes_hint")
        if hint:
            lines.append(f"  hint: {hint}")
        lines.append("")

    lines.append("=== VIEWS ===")
    for name, view in sorted((packet.get("views") or {}).items()):
        if not isinstance(view, dict):
            continue
        badge = view.get("status", UNKNOWN)
        lines.append(f"  [{badge:<24}] {name}")
        summary = view.get("summary")
        if isinstance(summary, dict) and summary:
            compact = ", ".join(
                f"{k}={v}"
                for k, v in list(summary.items())[:8]
                if not isinstance(v, (dict, list))
            )
            if compact:
                lines.append(f"      {compact}")
        if name == "frontier":
            ac = view.get("action_classes") or {}
            rk = view.get("rankings") or {}
            lines.append(
                f"      action_classes={ac.get('status')}  rankings={rk.get('status')}"
            )
            if ac.get("status") == UNKNOWN and not packet.get("agent"):
                lines.append(
                    "      tip: atlas-studio mc --agent <active_id> for F12 classes/ranks"
                )
    lines.append("")
    lines.append("=== ATTENTION (full; not authorization) ===")
    if not attention:
        lines.append("  (none)")
    else:
        for item in attention[:25]:
            lines.append(
                f"  tier={item.get('tier'):<3} [{item.get('kind')}] {item.get('title')}"
            )
    lines.append("")
    lines.append(
        "Badges: HEALTHY|DEGRADED|UNKNOWN|STALE|OFFLINE|BLOCKED|"
        "HUMAN_ATTENTION_REQUIRED"
    )
    return "\n".join(lines)
