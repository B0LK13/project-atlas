"""AS-STUDIO-A2-003 — Task Context + Continuation (read-only lens over ONE lane).

TASK_CONTEXT = PROJECTION (not authority)
LANE_STATE   = frontier + stack truth for one lane (atlas_dag builders; never re-derived)
KNOWLEDGE    = project_atlas read lenses (state / decisions / unknown) — KNOWN / UNKNOWN /
               STALE / CONFLICT / UNAVAILABLE stated explicitly, never guessed
NEXT_STEP    = the supported action and its prerequisites; a next step is not permission
CONTINUATION = pointers + fingerprints so another session resumes on the same truth
MISSING      = every input this packet did not have is listed, not silently defaulted

Composes AS-STUDIO-A1 Mission Control, AS-STUDIO-A2-002 Mission Journey and the Coder
Alpha lenses; adds no store, no ledger, no eligibility engine, no mutation surface.
Requirements served (#746 register): 06 Mission Control, 13 DAG/work graph,
20 Knowledge, 21 Decisions, 29 Offline/reconnect, 35 Bounded context, 39 Search,
44 Audit (continuation evidence), 50 Replay (inspection without side effects).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATTENTION_NE_AUTHORIZATION,
    GRANTS_NO_MUTATION,
    STALE_NE_CURRENT,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
    UNKNOWN_NE_HEALTHY,
)
from atlas_studio.snapshot import validator_for

SCHEMA_CONST = "ATLAS_STUDIO_TASK_CONTEXT_V1"
SCHEMA_FILE = "atlas_studio_task_context_v1.schema.json"
PACKAGE_ID = "AS-STUDIO-A2-003"

KNOWN = "KNOWN"
UNKNOWN = "UNKNOWN"
STALE = "STALE"
CONFLICT = "CONFLICT"
UNAVAILABLE = "UNAVAILABLE"

LIVE = "LIVE"
ACTION_OWNERSHIP_CLAIM = "OWNERSHIP_CLAIM"  # string only; no action_intent import

KNOWLEDGE_NE_PERMISSION = True
NEXT_STEP_NE_AUTHORIZATION = True
CONTINUATION_NE_EXECUTION = True
MISSING_SHOWN_EXPLICITLY = True
TASK_CONTEXT_NE_MUTATION = True

_LENS_SPECS: tuple[tuple[str, str, str], ...] = (
    ("state", "project_atlas.project_state", "build_state_lens"),
    ("decisions", "project_atlas.project_decisions", "build_decisions_lens"),
    ("unknown", "project_atlas.project_unknown", "build_unknown_lens"),
)


class TaskContextError(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "unknown_ne_healthy": UNKNOWN_NE_HEALTHY,
        "knowledge_ne_permission": KNOWLEDGE_NE_PERMISSION,
        "next_step_ne_authorization": NEXT_STEP_NE_AUTHORIZATION,
        "continuation_ne_execution": CONTINUATION_NE_EXECUTION,
        "missing_shown_explicitly": MISSING_SHOWN_EXPLICITLY,
        "task_context_ne_mutation": TASK_CONTEXT_NE_MUTATION,
    }


def validate_task_context(packet: dict) -> list[str]:
    validator = validator_for(SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def _fp(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def parse_lane(lane: str) -> tuple[str, int]:
    text = str(lane or "").strip()
    if not text.startswith("pr/") or not text[3:].isdigit() or int(text[3:]) < 1:
        raise TaskContextError(f"LANE_INVALID:{lane!r}")
    return text, int(text[3:])


# --- lane state (frontier + stack) -------------------------------------------


def project_lane_state(
    *,
    lane: str,
    frontier_matrix: dict | None,
    stacks: dict | None,
    agent_id: str | None,
    missing: list[str],
) -> dict[str, Any]:
    """One lane as the frontier/stack builders already see it. Never re-derives."""
    lane_s, pr = parse_lane(lane)
    rows = [
        a
        for a in ((frontier_matrix or {}).get("actions") or [])
        if str(a.get("lane")) == lane_s or a.get("pr") == pr
    ]
    if frontier_matrix is None:
        missing.append("NO_FRONTIER_MATRIX")
    if not rows:
        if frontier_matrix is not None:
            missing.append("LANE_NOT_IN_FRONTIER")
        identity: dict[str, Any] = {
            "pr": pr,
            "head": None,
            "tree": None,
            "ownership": UNKNOWN,
            "owner": None,
            "frozen": None,
            "ci_status": None,
            "iv_status": None,
        }
        status = UNKNOWN
    else:
        first = rows[0]
        identity = {
            "pr": pr,
            "head": first.get("head"),
            "tree": first.get("tree"),
            "ownership": first.get("ownership") or UNKNOWN,
            "owner": first.get("owner"),
            "frozen": first.get("frozen"),
            "ci_status": first.get("ci_status"),
            "iv_status": first.get("iv_status"),
        }
        status = KNOWN
    actions = [
        {
            "action_id": a.get("action_id"),
            "action_type": a.get("action_type"),
            "action_class": a.get("action_class"),
            "runnable_state": a.get("runnable_state"),
            "blocking_reasons": list(a.get("blocking_reasons") or []),
            "agent_eligible": bool(a.get("agent_eligible")),
            "score_total": a.get("score_total"),
        }
        for a in rows
    ]
    blockers = sorted({r for a in actions for r in a["blocking_reasons"]})

    stack_rec = (stacks or {}).get(lane_s) if isinstance(stacks, dict) else None
    if stacks is None:
        missing.append("NO_STACKS")
    if stack_rec:
        stack = {
            "status": KNOWN,
            "stack_root": stack_rec.get("stack_root"),
            "parent_pr": stack_rec.get("parent_pr"),
            "depth": stack_rec.get("depth"),
            "restack_required": bool(stack_rec.get("restack_required")),
        }
        depth = stack_rec.get("depth")
        if depth is None:
            impl = "STACK_CHAIN_BROKEN_DEPTH_UNKNOWN"
        elif stack_rec.get("parent_pr") is None:
            impl = "OPEN_LANE_BASED_ON_MAIN_NOT_MERGED"
        else:
            impl = f"OPEN_LANE_STACKED_DEPTH_{depth}_NOT_ON_MAIN"
    else:
        stack = {"status": UNKNOWN, "reason": "STACK_RECORD_ABSENT"}
        impl = UNKNOWN if not rows else "OPEN_LANE_NOT_ON_MAIN_STACK_UNKNOWN"

    dependencies: list[dict[str, Any]] = []
    if stack_rec and stack_rec.get("parent_pr") is not None:
        dependencies.append(
            {
                "kind": "parent_pr",
                "pr": stack_rec.get("parent_pr"),
                "note": "base lane must integrate first",
            }
        )
    if stack_rec and stack_rec.get("stack_root") and stack_rec.get("stack_root") != lane_s:
        dependencies.append(
            {
                "kind": "stack_root",
                "lane": stack_rec.get("stack_root"),
                "note": "root gate applies to the whole stack",
            }
        )

    owned_by_agent = (
        bool(agent_id) and identity["ownership"] == "OWNED" and identity["owner"] == agent_id
    )
    return {
        "status": status,
        "lane": lane_s,
        "identity": identity,
        "owned_by_agent": owned_by_agent,
        "actions": actions,
        "blockers": blockers,
        "dependencies": dependencies,
        "stack": stack,
        "implementation_vs_main": {
            "state": impl,
            "merged": UNKNOWN,
            "note": "an open lane's changes are not on main until merged; merge state is not "
            "derivable from the frontier and is left UNKNOWN",
        },
        "provenance": {
            "generator": "atlas_dag.frontier_matrix + atlas_dag.stack (via caller)",
            "frontier_fingerprint": (frontier_matrix or {}).get("frontier_fingerprint"),
            "authority": False,
        },
    }


# --- freshness with explanation -----------------------------------------------


def explain_freshness(
    *,
    mission_control: dict | None,
    frontier_matrix: dict | None,
    missing: list[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    if mission_control is None:
        missing.append("NO_MISSION_CONTROL")
        return {
            "state": UNKNOWN,
            "age_seconds": None,
            "max_age_seconds": None,
            "reasons": ["MISSION_CONTROL_ABSENT"],
            "fingerprints": {
                "mission_control": None,
                "frontier": (frontier_matrix or {}).get("frontier_fingerprint"),
            },
        }
    fres = mission_control.get("freshness") or {}
    state = str(fres.get("state") or UNKNOWN)
    if state != LIVE:
        reasons.append(f"MISSION_CONTROL_{state}")
    mc_frontier_fp = (mission_control.get("provenance") or {}).get("frontier_fingerprint")
    matrix_fp = (frontier_matrix or {}).get("frontier_fingerprint")
    if mc_frontier_fp and matrix_fp and mc_frontier_fp != matrix_fp:
        reasons.append("FRONTIER_FINGERPRINT_DIVERGED_FROM_MISSION_CONTROL")
        if state == LIVE:
            state = STALE
    if not matrix_fp:
        reasons.append("FRONTIER_FINGERPRINT_ABSENT")
    return {
        "state": state,
        "age_seconds": fres.get("age_seconds"),
        "max_age_seconds": fres.get("max_age_seconds"),
        "reasons": reasons,
        "fingerprints": {
            "mission_control": mission_control.get("snapshot_fingerprint"),
            "frontier": matrix_fp,
        },
    }


# --- knowledge (project_atlas read lenses) -----------------------------------


def _count(value: Any) -> int:
    """Lenses report some fields as lists and some as counts; treat both as counts."""
    if value is None:
        return 0
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _signal(entry: dict[str, Any], key: str) -> Any:
    """Read a lens field from ``signals`` first, then the top level.

    The real Coder Alpha lenses nest their counters under ``signals``
    (``{"signals": {"unresolved_conflicts": 0, ...}}``); only some fields
    (``decision_count``) sit at the top level. Reading one shape only made the
    classifier blind to real conflicts — caught by running the real lenses over
    a real vault, not by the injected-shape unit tests.
    """
    signals = entry.get("signals")
    if isinstance(signals, dict) and key in signals:
        return signals[key]
    return entry.get(key)


def _classify_lens(entry: dict[str, Any]) -> str:
    if _count(_signal(entry, "unresolved_conflicts")) > 0:
        return CONFLICT
    if _count(_signal(entry, "stale_claims")) > 0:
        return STALE
    counts = (
        _count(_signal(entry, "decision_count"))
        + _count(_signal(entry, "verified_claims"))
        + _count(_signal(entry, "unknown_items"))
    )
    if counts == 0 and str(entry.get("status") or "").lower() in {"", "unknown", "empty"}:
        return UNKNOWN
    if str(entry.get("status") or "").lower() == "unknown":
        return UNKNOWN
    return KNOWN


def _lens_summary(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "state": _classify_lens(entry),
        "lens_status": entry.get("status"),
        "summary": str(entry.get("summary") or "")[:240] or None,
        "authority": bool(entry.get("authority")) if entry.get("authority") is not None else False,
        "counts": {},
    }
    for key in (
        "decision_count",
        "active_governing_count",
        "verified_claims",
        "stale_claims",
        "unresolved_conflicts",
        "pending_reviews",
        "sources_failed",
    ):
        val = _signal(entry, key)
        if val is not None:
            summary["counts"][key] = len(val) if isinstance(val, list) else val
    if name == "decisions":
        sample = []
        for d in list(entry.get("decisions") or [])[:10]:
            if isinstance(d, dict):
                sample.append(
                    {
                        k: d.get(k)
                        for k in ("title", "kind", "status", "source", "subject")
                        if k in d
                    }
                )
        summary["decisions_sample"] = sample
    if name == "unknown":
        raw_unknown = _signal(entry, "unknown_items")
        summary["unknown_items"] = [
            (u if isinstance(u, str) else json.dumps(u, sort_keys=True, default=str))[:160]
            for u in (raw_unknown if isinstance(raw_unknown, list) else [])[:10]
        ]
        raw_conflicts = _signal(entry, "unresolved_conflicts")
        summary["unresolved_conflicts"] = (
            [
                (c if isinstance(c, str) else json.dumps(c, sort_keys=True, default=str))[:160]
                for c in raw_conflicts[:10]
            ]
            if isinstance(raw_conflicts, list)
            else _count(raw_conflicts)
        )
    return summary


def project_knowledge_lenses(
    *,
    vault: Path | str | None,
    project_id: str | None,
    missing: list[str],
    lens_builders: dict[str, Callable[[Path, str], dict]] | None = None,
) -> dict[str, Any]:
    """Read-only join of the Coder Alpha lenses. Never materializes; never invents."""
    if vault is None or not project_id:
        missing.append("NO_VAULT_BOUND" if vault is None else "NO_PROJECT_ID")
        return {
            "state": UNAVAILABLE,
            "reason": "NO_VAULT_BOUND" if vault is None else "NO_PROJECT_ID",
            "lenses": {},
            "provenance": {"authority": False},
        }
    vpath = Path(vault).expanduser()
    if not vpath.is_dir():
        missing.append("VAULT_NOT_A_DIRECTORY")
        return {
            "state": UNAVAILABLE,
            "reason": "VAULT_NOT_A_DIRECTORY",
            "lenses": {},
            "provenance": {"vault": str(vpath), "project_id": project_id, "authority": False},
        }
    builders: dict[str, Callable[[Path, str], dict]] = {}
    if lens_builders:
        builders.update(lens_builders)
    else:
        import importlib

        for name, module, func in _LENS_SPECS:
            try:
                builders[name] = getattr(importlib.import_module(module), func)
            except Exception as exc:
                builders[name] = _unavailable_builder(f"{type(exc).__name__}")
    lenses: dict[str, Any] = {}
    states: list[str] = []
    for name in ("state", "decisions", "unknown"):
        builder = builders.get(name) or _unavailable_builder("BUILDER_ABSENT")
        try:
            entry = builder(vpath, project_id)
            if not isinstance(entry, dict):
                raise TaskContextError("LENS_RETURN_INVALID")
            lenses[name] = _lens_summary(name, entry)
        except Exception as exc:
            lenses[name] = {
                "state": UNAVAILABLE,
                "reason": f"{type(exc).__name__}:{str(exc)[:120]}",
            }
        lenses[name]["provenance"] = {
            "generator": f"project_atlas.project_{name}.build_{name}_lens",
            "authority": False,
        }
        states.append(lenses[name]["state"])
    if CONFLICT in states:
        overall = CONFLICT
    elif STALE in states:
        overall = STALE
    elif all(s == UNAVAILABLE for s in states):
        overall = UNAVAILABLE
    elif KNOWN in states:
        overall = KNOWN
    else:
        overall = UNKNOWN
    return {
        "state": overall,
        "lenses": lenses,
        "provenance": {
            "vault": str(vpath),
            "project_id": project_id,
            "authority": False,
            "reuse": "project_atlas read lenses; no parallel store",
        },
    }


def _unavailable_builder(reason: str) -> Callable[[Path, str], dict]:
    def _raise(_vault: Path, _pid: str) -> dict:
        raise TaskContextError(f"LENS_UNAVAILABLE:{reason}")

    return _raise


# --- next step, recovery, continuation ---------------------------------------


def supported_next_step(*, lane_state: dict[str, Any], agent_id: str | None) -> dict[str, Any]:
    runnable = [
        a
        for a in lane_state.get("actions") or []
        if a.get("runnable_state") == "RUNNABLE" and a.get("agent_eligible")
    ]
    ownership = (lane_state.get("identity") or {}).get("ownership")
    owner = (lane_state.get("identity") or {}).get("owner")
    lane = lane_state.get("lane")
    if not runnable:
        reasons = list(lane_state.get("blockers") or [])
        if lane_state.get("status") != KNOWN:
            reasons.append("LANE_STATE_UNKNOWN")
        if not agent_id:
            reasons.append("AGENT_UNBOUND")
        return {
            "status": "NO_SUPPORTED_ACTION",
            "action": None,
            "reasons": sorted(set(reasons)) or ["NO_RUNNABLE_ELIGIBLE_ACTION"],
            "authorization": "NOT_GRANTED_BY_THIS_PACKET",
        }
    best = max(
        runnable, key=lambda a: (float(a.get("score_total") or 0.0), str(a.get("action_id")))
    )
    prereqs: list[str] = list(best.get("blocking_reasons") or [])
    hint = None
    if best.get("action_type") == ACTION_OWNERSHIP_CLAIM:
        prereqs += [
            "CLAIM_INTENT_MINTED_FROM_LIVE_MISSION_CONTROL",
            "EXPLICIT_REPO_PIN_AT_EXECUTE",
            "CONTROL_PLANE_REVALIDATION_AT_EXECUTE",
        ]
        if ownership == "OWNED" and owner != agent_id:
            prereqs.append(f"LANE_OWNED_BY_OTHER:{owner}")
        hint = f"atlas-studio claim-preview --agent {agent_id or '<agent>'} --lane {lane}"
    return {
        "status": "SUPPORTED",
        "action": {
            k: best.get(k)
            for k in ("action_id", "action_type", "action_class", "runnable_state", "score_total")
        },
        "prerequisites": sorted(set(prereqs)),
        "preview_command": hint,
        "authorization": "NOT_GRANTED_BY_THIS_PACKET",
        "note": "preview != execution; execution revalidates against the control plane",
    }


def recovery_guidance(
    *, lane_state: dict[str, Any], freshness: dict[str, Any], knowledge: dict[str, Any]
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if freshness.get("state") != LIVE:
        out.append(
            {
                "condition": f"FRESHNESS_{freshness.get('state')}",
                "guidance": "Rebuild Mission Control before minting or evaluating an intent; "
                "fingerprints bound to this packet will be refused as REFUSED_STALE.",
            }
        )
    ident = lane_state.get("identity") or {}
    if ident.get("ownership") == "AMBIGUOUS":
        out.append(
            {
                "condition": "OWNERSHIP_AMBIGUOUS",
                "guidance": "More than one active claimant: do not write; a human or the "
                "control plane must release one claim first.",
            }
        )
    if lane_state.get("status") != KNOWN:
        out.append(
            {
                "condition": "LANE_UNKNOWN",
                "guidance": "The lane is not in the frontier for this agent; confirm the PR is "
                "open and the agent is registered before acting.",
            }
        )
    if knowledge.get("state") in {UNAVAILABLE, UNKNOWN}:
        out.append(
            {
                "condition": f"KNOWLEDGE_{knowledge.get('state')}",
                "guidance": "Bind a compiled vault (--vault/--project) or run the Atlas "
                "pipeline; absent knowledge is not permission to guess.",
            }
        )
    if knowledge.get("state") == CONFLICT:
        out.append(
            {
                "condition": "KNOWLEDGE_CONFLICT",
                "guidance": "Unresolved conflicts exist in the decision record; resolve through "
                "`atlas review decide` before relying on either side.",
            }
        )
    out.append(
        {
            "condition": "UNCERTAIN_MUTATION",
            "guidance": "If a prior claim-execute returned EXECUTION_FAILED "
            "(mutation_state=UNKNOWN), inspect the bus (`atlas-dag owners`) "
            "before any retry; never auto-retry.",
        }
    )
    return out


def build_continuation(
    *,
    lane_state: dict[str, Any],
    freshness: dict[str, Any],
    agent_id: str | None,
    vault: Path | str | None,
    project_id: str | None,
    include_agent_context: bool,
    agent_context_fn: Callable[..., dict] | None,
    missing: list[str],
) -> dict[str, Any]:
    ident = lane_state.get("identity") or {}
    pr = ident.get("pr")
    cont: dict[str, Any] = {
        "coordination_handoff": {
            "schema": "ATLAS_HANDOFF_V1",
            "command": f"atlas-dag handoff {pr} --mode resume" if pr else None,
            "live_required": True,
            "built_here": False,
        },
        "knowledge_handoff": {
            "schema": "atlas handoff (project_atlas.agent_handoff.create_handoff)",
            "command": (
                f"atlas handoff create --vault {vault} --project {project_id}"
                if vault and project_id
                else None
            ),
            "available": bool(vault and project_id),
            "built_here": False,
        },
        "agent_context": {"status": "NOT_REQUESTED"},
        "fingerprints": {
            "lane_head": ident.get("head"),
            "lane_tree": ident.get("tree"),
            "mission_control": (freshness.get("fingerprints") or {}).get("mission_control"),
            "frontier": (freshness.get("fingerprints") or {}).get("frontier"),
        },
        "resume_checklist": [
            "re-run task-context and compare fingerprints before trusting this packet",
            "confirm lane head unchanged (a moved head invalidates evidence)",
            "confirm ownership on the bus (atlas-dag owners) before any write",
            "never replay a recorded execution; new effects need new authority",
        ],
    }
    if include_agent_context:
        if not (vault and project_id):
            cont["agent_context"] = {"status": UNAVAILABLE, "reason": "NO_VAULT_BOUND"}
            missing.append("AGENT_CONTEXT_NO_VAULT")
        else:
            fn = agent_context_fn
            if fn is None:
                try:
                    from project_atlas.agent_handoff import (  # type: ignore[assignment]
                        export_agent_context as fn,
                    )
                except Exception as exc:
                    fn = None
                    cont["agent_context"] = {"status": UNAVAILABLE, "reason": type(exc).__name__}
            if fn is not None:
                try:
                    exported = fn(Path(vault), project_id, refresh_brief=False)
                    cont["agent_context"] = {
                        "status": str(exported.get("status") or "EXPORTED"),
                        "next": exported.get("next"),
                        "json_path": exported.get("json_path"),
                        "markdown_path": exported.get("markdown_path"),
                        "freshness": exported.get("freshness"),
                        "lens_is_authority": bool(exported.get("lens_is_authority", False)),
                    }
                except Exception as exc:
                    cont["agent_context"] = {
                        "status": UNAVAILABLE,
                        "reason": f"{type(exc).__name__}:{str(exc)[:120]}",
                    }
    cont["fingerprint"] = _fp({k: v for k, v in cont.items() if k != "fingerprint"})
    return cont


# --- packet --------------------------------------------------------------------


def build_task_context(
    *,
    lane: str,
    agent_id: str | None = None,
    mission_control: dict | None = None,
    frontier_matrix: dict | None = None,
    stacks: dict | None = None,
    vault: Path | str | None = None,
    project_id: str | None = None,
    include_agent_context: bool = False,
    journey: dict | None = None,
    lens_builders: dict[str, Callable[[Path, str], dict]] | None = None,
    agent_context_fn: Callable[..., dict] | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Assemble the packet from already-built truth. Never mutates its inputs."""
    missing: list[str] = []
    lane_s, _pr = parse_lane(lane)
    lane_state = project_lane_state(
        lane=lane_s,
        frontier_matrix=frontier_matrix,
        stacks=stacks,
        agent_id=agent_id,
        missing=missing,
    )
    freshness = explain_freshness(
        mission_control=mission_control, frontier_matrix=frontier_matrix, missing=missing
    )
    knowledge = project_knowledge_lenses(
        vault=vault, project_id=project_id, missing=missing, lens_builders=lens_builders
    )
    next_step = supported_next_step(lane_state=lane_state, agent_id=agent_id)
    recovery = recovery_guidance(lane_state=lane_state, freshness=freshness, knowledge=knowledge)
    continuation = build_continuation(
        lane_state=lane_state,
        freshness=freshness,
        agent_id=agent_id,
        vault=vault,
        project_id=project_id,
        include_agent_context=include_agent_context,
        agent_context_fn=agent_context_fn,
        missing=missing,
    )
    if not agent_id:
        missing.append("NO_AGENT_BOUND")
    attention = []
    for item in (mission_control or {}).get("attention") or []:
        refs = item.get("references") or []
        hit = any(
            str(r.get("id") or "").startswith(f"{lane_s}:") or r.get("id") == lane_s
            for r in refs
            if isinstance(r, dict)
        )
        if hit or item.get("lane") == lane_s:
            attention.append(
                {k: item.get(k) for k in ("attention_id", "kind", "tier", "summary") if k in item}
                | {"attention_ne_authorization": True}
            )
    journey_ref = None
    if journey is not None:
        journey_ref = {
            "schema": journey.get("schema"),
            "mission_status": (journey.get("mission") or {}).get("mission_status"),
            "knowledge_state": (journey.get("knowledge") or {}).get("state"),
            "snapshot_fingerprint": (journey.get("mission") or {}).get("snapshot_fingerprint"),
        }
    packet: dict[str, Any] = {
        "schema": SCHEMA_CONST,
        "package": PACKAGE_ID,
        "generated_at_utc": clock(),
        "repository": (mission_control or {}).get("repository"),
        "agent": agent_id,
        "lane": lane_s,
        "freshness": freshness,
        "lane_state": lane_state,
        "attention": attention,
        "knowledge": knowledge,
        "next_step": next_step,
        "recovery": recovery,
        "continuation": continuation,
        "journey_ref": journey_ref,
        "missing": sorted(set(missing)),
        "honesty": honesty_block(),
        "provenance": {
            "generator": f"atlas-studio task-context ({PACKAGE_ID})",
            "presentation_only": True,
            "grants_no_mutation": True,
            "truth_sources": [
                "atlas_dag.frontier_matrix.build_frontier_matrix",
                "atlas_dag.stack.build_stacks",
                "atlas_studio.mission_control.build_mission_control",
                "project_atlas.project_state.build_state_lens",
                "project_atlas.project_decisions.build_decisions_lens",
                "project_atlas.project_unknown.build_unknown_lens",
                "project_atlas.agent_handoff.export_agent_context (optional)",
            ],
        },
    }
    packet["fingerprint"] = _fp(
        {k: v for k, v in packet.items() if k not in {"fingerprint", "generated_at_utc"}}
    )
    return packet


def format_task_context_tui(packet: dict) -> str:
    ls = packet.get("lane_state") or {}
    ident = ls.get("identity") or {}
    fres = packet.get("freshness") or {}
    kn = packet.get("knowledge") or {}
    nxt = packet.get("next_step") or {}
    lines = [
        f"TASK CONTEXT {packet.get('lane')}  repo={packet.get('repository')}  "
        f"agent={packet.get('agent')}",
        f"  freshness={fres.get('state')} reasons={','.join(fres.get('reasons') or []) or '-'}",
        f"  lane={ls.get('status')} head={(ident.get('head') or '')[:12] or '-'} "
        f"ownership={ident.get('ownership')} owner={ident.get('owner') or '-'} "
        f"ci={ident.get('ci_status') or '-'} iv={ident.get('iv_status') or '-'}",
        f"  vs_main={(ls.get('implementation_vs_main') or {}).get('state')} "
        f"blockers={','.join(ls.get('blockers') or []) or '-'}",
        f"  knowledge={kn.get('state')} "
        + " ".join(f"{k}={v.get('state')}" for k, v in (kn.get("lenses") or {}).items()),
        f"  next_step={nxt.get('status')} "
        f"action={(nxt.get('action') or {}).get('action_id') or '-'} "
        f"prereqs={','.join(nxt.get('prerequisites') or []) or '-'}",
        f"  missing={','.join(packet.get('missing') or []) or '-'}",
        f"  fingerprint={(packet.get('fingerprint') or '')[:12]}…",
        "HONESTY: TASK_CONTEXT!=AUTHORITY / NEXT_STEP!=AUTHORIZATION / CONTINUATION!=EXECUTION",
    ]
    for r in packet.get("recovery") or []:
        lines.append(f"  recover[{r.get('condition')}]: {r.get('guidance')}")
    return "\n".join(lines)


__all__ = [
    "PACKAGE_ID",
    "SCHEMA_CONST",
    "TaskContextError",
    "build_continuation",
    "build_task_context",
    "explain_freshness",
    "format_task_context_tui",
    "honesty_block",
    "project_knowledge_lenses",
    "project_lane_state",
    "recovery_guidance",
    "supported_next_step",
    "validate_task_context",
]
