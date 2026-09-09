"""AS-STUDIO-A2-002 — read-only Mission Journey vertical slice.

MISSION_JOURNEY = PROJECTION (not authority)
KNOWLEDGE != PERMISSION
DEVELOPMENT_CONTEXT != AUTHORIZATION
PREVIEW != EXECUTION
STUDIO_UI != AUTHORITY
A1_READ_ONLY = PRESERVED
A2_CLAIM_REUSED = YES (candidates/preview only; no execute here)

Composes Mission Control + knowledge provenance states + development
context + existing OWNERSHIP_CLAIM candidates/preview into one
ATLAS_STUDIO_MISSION_JOURNEY_V1 packet.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
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
from atlas_studio.mission_control import (
    SCHEMA_CONST as MC_SCHEMA,
    build_mission_control,
    validate_mission_control,
)
from atlas_studio.snapshot import utcnow, validator_for

SCHEMA_CONST = "ATLAS_STUDIO_MISSION_JOURNEY_V1"
SCHEMA_FILE = "atlas_studio_mission_journey_v1.schema.json"

# Knowledge plane retrieval honesty states (directive §6).
RETRIEVED = "RETRIEVED"
NONE_FOUND = "NONE_FOUND"
UNAVAILABLE = "UNAVAILABLE"
STALE = "STALE"
INCOMPLETE = "INCOMPLETE"

_KNOWLEDGE_STATES = frozenset(
    {RETRIEVED, NONE_FOUND, UNAVAILABLE, STALE, INCOMPLETE}
)

_DEFAULT_CLOSED = (
    "CI_DISPATCH",
    "IV_REQUEST",
    "HANDOFF_DELIVER",
    "STEAL_EXECUTE",
    "MERGE",
    "WORKTREE_OPEN",
)

# Relative paths under a docs root that are mission-relevant for Studio.
_DEFAULT_DOC_GLOBS = (
    "atlas-3/studio/**/*.md",
    "adr/ADR-034*.md",
    "adr/ADR-035*.md",
)


def honesty_block() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "ui_state_is_projection": UI_STATE_IS_PROJECTION,
        "grants_no_mutation": GRANTS_NO_MUTATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
        "unknown_ne_healthy": UNKNOWN_NE_HEALTHY,
        "knowledge_ne_permission": True,
        "development_context_ne_authorization": True,
        "preview_ne_execution": True,
        "journey_ne_mutation": True,
        "a1_read_only_preserved": True,
    }


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_mission_journey(packet: dict) -> list[str]:
    validator = validator_for(SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def _mission_section(mc: dict) -> dict[str, Any]:
    freshness = mc.get("freshness") or {}
    if not isinstance(freshness, dict):
        freshness = {"state": str(freshness)}
    attention = mc.get("attention")
    if isinstance(attention, list):
        items = list(attention)
    elif isinstance(attention, dict):
        items = list(attention.get("items") or [])
    else:
        items = []
    return {
        "mission_status": mc.get("mission_status"),
        "slice_status": mc.get("slice_status"),
        "freshness_state": freshness.get("state") or freshness.get("status") or "UNKNOWN",
        "snapshot_fingerprint": mc.get("snapshot_fingerprint"),
        "attention_count": len(items),
        "top_attention": items[:5],
        "mc_schema": mc.get("schema"),
    }


def project_knowledge(
    *,
    docs_root: Path | str | None = None,
    injected_items: list[dict[str, Any]] | None = None,
    force_state: str | None = None,
    max_items: int = 12,
) -> dict[str, Any]:
    """Project mission-relevant documentation with provenance honesty.

    Does **not** create a parallel knowledge store. Prefers injected fixtures
    for deterministic tests; otherwise scans an optional docs root for Studio
    ADR / phase notes. Retrieved content is data, never permission.
    """
    notes: list[str] = ["knowledge_ne_permission", "reuse:filesystem_docs_projection"]
    if force_state is not None:
        if force_state not in _KNOWLEDGE_STATES:
            raise ValueError(f"invalid knowledge force_state:{force_state}")
        return {
            "state": force_state,
            "items": list(injected_items or []),
            "notes": notes + [f"forced_state:{force_state}"],
        }

    if injected_items is not None:
        items = list(injected_items)
        state = RETRIEVED if items else NONE_FOUND
        return {"state": state, "items": items[:max_items], "notes": notes + ["injected"]}

    if docs_root is None:
        return {
            "state": UNAVAILABLE,
            "items": [],
            "notes": notes + ["DOCS_ROOT_NOT_SUPPLIED"],
        }

    root = Path(docs_root)
    if not root.is_dir():
        return {
            "state": UNAVAILABLE,
            "items": [],
            "notes": notes + [f"DOCS_ROOT_MISSING:{root}"],
        }

    items: list[dict[str, Any]] = []
    try:
        for pattern in _DEFAULT_DOC_GLOBS:
            for path in sorted(root.glob(pattern)):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(root)).replace("\\", "/")
                kind = _classify_doc(rel)
                items.append(
                    {
                        "path": rel,
                        "kind": kind,
                        "title": path.stem,
                        "provenance": {
                            "source_path": rel,
                            "generator": "atlas_studio.mission_journey.project_knowledge",
                            "authority": False,
                        },
                    }
                )
                if len(items) >= max_items:
                    break
            if len(items) >= max_items:
                break
    except OSError as exc:
        return {
            "state": UNAVAILABLE,
            "items": [],
            "notes": notes + [f"DOCS_SCAN_ERROR:{type(exc).__name__}"],
        }

    if not items:
        return {"state": NONE_FOUND, "items": [], "notes": notes + ["scan_empty"]}

    # Truncation ⇒ incomplete (more docs may exist beyond max_items).
    truncated = False
    try:
        total = sum(1 for pattern in _DEFAULT_DOC_GLOBS for p in root.glob(pattern) if p.is_file())
        truncated = total > len(items)
    except OSError:
        truncated = True
        notes.append("COUNT_INCOMPLETE")

    state = INCOMPLETE if truncated else RETRIEVED
    if truncated:
        notes.append("TRUNCATED_TO_MAX_ITEMS")
    return {"state": state, "items": items, "notes": notes}


def _classify_doc(rel: str) -> str:
    lower = rel.lower()
    if "adr" in lower:
        return "decision"
    if "evidence" in lower or "iv" in lower:
        return "evidence"
    if "requirement" in lower or "register" in lower:
        return "requirement"
    if "threat" in lower or "finding" in lower:
        return "finding"
    return "mission_doc"


def project_development(
    *,
    mission_control: dict,
    claim_listing: dict | None = None,
) -> dict[str, Any]:
    """Development-plane projection from MC + claim listing (no new eligibility)."""
    repo = mission_control.get("repository")
    freshness = mission_control.get("freshness") or {}
    snap = mission_control.get("studio_snapshot") or {}
    candidates = list((claim_listing or {}).get("candidates") or [])
    prerequisites: list[str] = [
        "mission_control_packet",
        "repository_identity",
        "agent_bind_for_claim_when_mutating",
    ]
    missing: list[str] = []
    if not repo:
        missing.append("repository_identity")
    fres = str(freshness.get("state") or freshness.get("status") or "")
    if fres in {"STALE", "OFFLINE", "UNKNOWN"}:
        missing.append(f"freshness_not_current:{fres or 'UNKNOWN'}")
    if claim_listing is None:
        missing.append("claim_candidates_projection")

    return {
        "repository": repo,
        "candidate_identity": {
            "agent": mission_control.get("agent"),
            "agent_status": mission_control.get("agent_status"),
            "snapshot_fingerprint": mission_control.get("snapshot_fingerprint"),
            "studio_slice_status": snap.get("slice_status") or mission_control.get("slice_status"),
            "claim_candidate_count": len(candidates),
            "top_claim_lanes": [
                {
                    "lane": c.get("lane") or c.get("target_lane"),
                    "pr": c.get("pr") or c.get("target_pr"),
                    "action_class": c.get("action_class"),
                }
                for c in candidates[:5]
            ],
        },
        "prerequisites": prerequisites,
        "missing_prerequisites": missing,
        "supported_capabilities": ["OWNERSHIP_CLAIM"],
        "closed_capabilities": list(_DEFAULT_CLOSED),
    }


def build_mission_journey(
    *,
    agent_id: str | None = None,
    repo: str | None = None,
    mission_control: dict | None = None,
    claim_listing: dict | None = None,
    preview: dict | None = None,
    preview_lane: str | None = None,
    docs_root: Path | str | None = None,
    knowledge_items: list[dict[str, Any]] | None = None,
    knowledge_force_state: str | None = None,
    live: bool = False,
    verifier_pool_path: Path | str | None = None,
    weights_path: Path | str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build ATLAS_STUDIO_MISSION_JOURNEY_V1. Never mutates; never executes claims."""
    from atlas_studio import action_intent as gc

    notes: list[str] = [
        "package:AS-STUDIO-A2-002",
        "journey_ne_mutation",
        "reuse:mission_control",
        "reuse:action_intent.list_claim_candidates",
    ]

    mc = mission_control
    if mc is None:
        mc = build_mission_control(
            agent_id=agent_id,
            live=live,
            repo=repo,
            verifier_pool_path=verifier_pool_path,
            weights_path=weights_path,
            clock=clock,
        )
        notes.append("mc_built")
    else:
        notes.append("mc_injected")

    mc_errors = validate_mission_control(mc)
    if mc_errors:
        notes.append(f"MC_SCHEMA_WARN:{len(mc_errors)}")

    listing = claim_listing
    if listing is None:
        listing = gc.list_claim_candidates(
            agent_id=agent_id or mc.get("agent"),
            frontier_matrix=None,
            mission_control=mc,
            live=False,
            repo=repo or mc.get("repository"),
            clock=clock,
        )
        # Prefer matrix nested under MC views when present.
        views = mc.get("views") or {}
        frontier = views.get("frontier") or {}
        matrix = frontier.get("matrix") or mc.get("frontier_matrix")
        if matrix is not None:
            listing = gc.list_claim_candidates(
                agent_id=agent_id or mc.get("agent"),
                frontier_matrix=matrix,
                mission_control=mc,
                clock=clock,
            )
            notes.append("claim_listing_from_mc_frontier")
        else:
            notes.append("claim_listing_matrix_absent_or_empty")

    attached_preview = preview
    if attached_preview is None and preview_lane:
        try:
            attached_preview = gc.preview_ownership_claim(
                agent_id=str(agent_id or mc.get("agent") or ""),
                lane=preview_lane,
                frontier_matrix=(mc.get("views") or {}).get("frontier", {}).get("matrix"),
                mission_control=mc,
                clock=clock,
            )
            notes.append("preview_attached")
        except Exception as exc:  # noqa: BLE001 — journey must degrade
            attached_preview = None
            notes.append(f"PREVIEW_UNAVAILABLE:{type(exc).__name__}")

    knowledge = project_knowledge(
        docs_root=docs_root,
        injected_items=knowledge_items,
        force_state=knowledge_force_state,
    )
    development = project_development(mission_control=mc, claim_listing=listing)
    mission = _mission_section(mc)

    # If MC freshness is stale, knowledge cannot be claimed current even if scanned.
    fres = str(mission.get("freshness_state") or "")
    if fres == "STALE" and knowledge["state"] == RETRIEVED:
        knowledge = {
            **knowledge,
            "state": STALE,
            "notes": list(knowledge.get("notes") or []) + ["MC_FRESHNESS_STALE"],
        }

    packet = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "repository": mc.get("repository") or repo,
        "agent": agent_id or mc.get("agent"),
        "mission": mission,
        "knowledge": knowledge,
        "development": development,
        "next_actions": {
            "claim_candidates": listing,
            "preview": attached_preview,
            "monitoring": {
                "command": (
                    "atlas-studio action-evidence --decision-file <decision.json> [--json]"
                ),
                "optional_spool": (
                    "atlas-studio action-evidence --decision-file <decision.json> "
                    "--write-spool --spool-dir <dir>"
                ),
                "package": "AS-STUDIO-A2-004",
                "auto_retry": False,
                "notes": [
                    "MONITOR!=RE-EXECUTE",
                    "AUTO_RETRY=FORBIDDEN",
                    "CAPTURE!=AUTHORITY",
                    "inspect EXECUTION_FAILED before any fresh intent",
                    "use intent-continuity after interrupt/stale/duplicate risk",
                ],
            },
            "continuity": {
                "command": (
                    "atlas-studio intent-continuity --intent-file <intent.json> "
                    "[--decision-file <decision.json>]"
                ),
                "package": "AS-STUDIO-A2-005",
                "auto_retry": False,
                "notes": [
                    "STALE_INTENT!=PERMISSION",
                    "DUPLICATE_SUBMIT!=AUTO_RETRY",
                    "INSPECT!=EXECUTE",
                ],
            },
            "notes": [
                "PREVIEW!=EXECUTION",
                "AVAILABLE!=AUTHORIZED",
                "use claim-evaluate/claim-execute for gated mutation",
                "use action-evidence after evaluate/execute to monitor/recover",
            ],
        },
        "honesty": honesty_block(),
        "provenance": {
            "generator": "atlas-studio mission-journey (AS-STUDIO-A2-002)",
            "presentation_only": True,
            "grants_no_mutation": True,
            "truth_sources": [
                MC_SCHEMA,
                "atlas_studio.action_intent.list_claim_candidates",
                "atlas_studio.mission_journey.project_knowledge",
            ],
            "notes": notes,
            "journey_fingerprint": None,
        },
    }
    # Fingerprint excluding itself for stability.
    fp_material = {k: v for k, v in packet.items() if k != "provenance"}
    packet["provenance"]["journey_fingerprint"] = _canonical_sha256(fp_material)
    return packet


def format_mission_journey_tui(packet: dict) -> str:
    """Human-readable RO projection. Not authority."""
    mission = packet.get("mission") or {}
    knowledge = packet.get("knowledge") or {}
    development = packet.get("development") or {}
    next_actions = packet.get("next_actions") or {}
    listing = next_actions.get("claim_candidates") or {}
    candidates = list(listing.get("candidates") or [])
    lines = [
        f"atlas-studio mission-journey schema={packet.get('schema')}",
        f"repository={packet.get('repository')} agent={packet.get('agent')}",
        f"mission_status={mission.get('mission_status')} "
        f"freshness={mission.get('freshness_state')} "
        f"attention={mission.get('attention_count')}",
        f"knowledge_state={knowledge.get('state')} "
        f"items={len(knowledge.get('items') or [])}",
        f"development_repo={development.get('repository')} "
        f"missing={list(development.get('missing_prerequisites') or [])}",
        f"claim_candidates={len(candidates)} "
        f"preview_attached={next_actions.get('preview') is not None}",
        f"monitoring={((next_actions.get('monitoring') or {}).get('command') or 'none')}",
        "HONESTY: STUDIO_UI!=AUTHORITY / KNOWLEDGE!=PERMISSION / "
        "PREVIEW!=EXECUTION / JOURNEY!=MUTATION / MONITOR!=RE-EXECUTE",
    ]
    for item in (knowledge.get("items") or [])[:5]:
        lines.append(f"  knowledge: [{item.get('kind')}] {item.get('path')}")
    for cand in candidates[:5]:
        lane = cand.get("lane") or cand.get("target_lane")
        lines.append(f"  claim_candidate: lane={lane} pr={cand.get('pr') or cand.get('target_pr')}")
    return "\n".join(lines)
