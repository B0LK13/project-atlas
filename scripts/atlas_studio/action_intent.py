"""AS-STUDIO-A2-001 — governed OWNERSHIP_CLAIM intent path.

STUDIO_UI != AUTHORITY
REQUESTED != CLAIMED
PREVIEW != EXECUTION
STALE_INTENT != CURRENT_PERMISSION
CONTROL_PLANE_REVALIDATES_AT_EXECUTION
BUTTON != MUTATION
A1_TRUTH_BOUNDARY = PRESERVED

Studio produces typed intents and previews. The control-plane evaluate step
revalidates live truth, then may invoke atlas_dag emitter OWNER_CLAIMED.
Studio never self-authorizes. Dispatch / steal-auto / merge / IV are out of
scope for this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATTENTION_NE_AUTHORIZATION,
    STALE_NE_CURRENT,
    STUDIO_UI_NE_AUTHORITY,
)
from atlas_studio.snapshot import SCHEMA_DIR, validator_for

SCHEMA_INTENT = "ATLAS_STUDIO_ACTION_INTENT_V1"
SCHEMA_PREVIEW = "ATLAS_STUDIO_ACTION_PREVIEW_V1"
SCHEMA_DECISION = "ATLAS_STUDIO_ACTION_DECISION_V1"

INTENT_SCHEMA_FILE = "atlas_studio_action_intent_v1.schema.json"
PREVIEW_SCHEMA_FILE = "atlas_studio_action_preview_v1.schema.json"
DECISION_SCHEMA_FILE = "atlas_studio_action_decision_v1.schema.json"

ACTION_OWNERSHIP_CLAIM = "OWNERSHIP_CLAIM"

DEFAULT_MAX_AGE_SECONDS = 120

# Decision vocabulary (evaluate / execute).
EXECUTE_ALLOWED = "EXECUTE_ALLOWED"
EXECUTED = "EXECUTED"
REFUSED_STALE = "REFUSED_STALE"
REFUSED_ALREADY_OWNED = "REFUSED_ALREADY_OWNED"
REFUSED_NOT_RUNNABLE = "REFUSED_NOT_RUNNABLE"
REFUSED_AGENT_INVALID = "REFUSED_AGENT_INVALID"
REFUSED_CAPABILITY = "REFUSED_CAPABILITY"
REFUSED_POLICY = "REFUSED_POLICY"
REFUSED_TARGET_MISMATCH = "REFUSED_TARGET_MISMATCH"
REFUSED_IDEMPOTENT_ALREADY_CLAIMED = "REFUSED_IDEMPOTENT_ALREADY_CLAIMED"
REFUSED_SCHEMA = "REFUSED_SCHEMA"
EXECUTION_FAILED = "EXECUTION_FAILED"  # substrate: executor raised / invalid return

FORBIDDEN_AUTHZ_FIELDS = frozenset(
    {
        "authorized",
        "permitted",
        "executable",
        "grants",
        "policy_pass",
        "authorization_granted",
        "authorization_required",  # sketch field; Studio must not mint grants
    }
)

_LANE_RE = re.compile(r"^pr/([1-9][0-9]*)$")

REQUESTED_NE_CLAIMED = True
PREVIEW_NE_EXECUTION = True
CAPABILITY_CLAIMS_NE_AUTHORIZATION = True
GRANTS_NO_SELF_AUTHORIZATION = True
CONTROL_PLANE_REVALIDATES_AT_EXECUTION = True
STUDIO_NEVER_SELF_AUTHORIZES = True
STALE_INTENT_NE_CURRENT_PERMISSION = True
DISPATCH_STEAL_AUTO_NOT_STARTED = True


class GovernedClaimError(RuntimeError):
    """Fail-closed governed claim failure."""


def honesty_intent() -> dict[str, bool]:
    return {
        "requested_ne_claimed": REQUESTED_NE_CLAIMED,
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "capability_claims_ne_authorization": CAPABILITY_CLAIMS_NE_AUTHORIZATION,
        "grants_no_self_authorization": GRANTS_NO_SELF_AUTHORIZATION,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "stale_ne_current": STALE_NE_CURRENT,
    }


def honesty_preview() -> dict[str, bool]:
    return {
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "requested_ne_claimed": REQUESTED_NE_CLAIMED,
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "attention_ne_authorization": ATTENTION_NE_AUTHORIZATION,
        "grants_no_mutation": True,
    }


def honesty_decision() -> dict[str, bool]:
    return {
        "studio_ui_ne_authority": STUDIO_UI_NE_AUTHORITY,
        "requested_ne_claimed": REQUESTED_NE_CLAIMED,
        "preview_ne_execution": PREVIEW_NE_EXECUTION,
        "control_plane_revalidates_at_execution": CONTROL_PLANE_REVALIDATES_AT_EXECUTION,
        "studio_never_self_authorizes": STUDIO_NEVER_SELF_AUTHORIZES,
        "stale_intent_ne_current_permission": STALE_INTENT_NE_CURRENT_PERMISSION,
    }


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(UTC)


def parse_lane(lane: str) -> tuple[str, int]:
    match = _LANE_RE.match(str(lane).strip())
    if not match:
        raise GovernedClaimError(f"INVALID_LANE:{lane}")
    pr = int(match.group(1))
    return f"pr/{pr}", pr


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _reject_authz_fields(payload: dict) -> list[str]:
    bad = sorted(k for k in payload if k in FORBIDDEN_AUTHZ_FIELDS)
    if not bad:
        return []
    return [f"FORBIDDEN_AUTHZ_FIELD:{k}" for k in bad]


def validate_intent(packet: dict) -> list[str]:
    errors = _reject_authz_fields(packet)
    # executable=true even if somehow present under additionalProperties path
    if packet.get("executable") is True:
        errors.append("FORBIDDEN_AUTHZ_FIELD:executable=true")
    validator = validator_for(INTENT_SCHEMA_FILE)
    errors.extend(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )
    return errors


def validate_preview(packet: dict) -> list[str]:
    validator = validator_for(PREVIEW_SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def validate_decision(packet: dict) -> list[str]:
    validator = validator_for(DECISION_SCHEMA_FILE)
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    ]


def schemas_loadable() -> tuple[bool, str]:
    try:
        for name in (INTENT_SCHEMA_FILE, PREVIEW_SCHEMA_FILE, DECISION_SCHEMA_FILE):
            path = SCHEMA_DIR / name
            if not path.is_file():
                return False, f"missing:{name}"
            json.loads(path.read_text(encoding="utf-8"))
            validator_for(name)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}:{exc}"


def _decision(
    decision: str,
    *,
    intent_id: str | None,
    reasons: list[str],
    evidence: dict[str, Any] | None = None,
    mutated: bool = False,
    dry_run: bool = False,
    emit_status: str | None = None,
    event_id: str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    packet = {
        "schema": SCHEMA_DECISION,
        "decision": decision,
        "action_type": ACTION_OWNERSHIP_CLAIM,
        "intent_id": intent_id,
        "mutated": mutated,
        "dry_run": dry_run,
        "emit_status": emit_status,
        "event_id": event_id,
        "reasons": sorted(reasons),
        "evidence": evidence or {},
        "evaluated_at_utc": clock(),
        "honesty": honesty_decision(),
    }
    return packet


def _find_claim_action(matrix: dict | None, *, lane: str, agent_id: str) -> dict | None:
    if not isinstance(matrix, dict):
        return None
    matches: list[dict] = []
    for action in matrix.get("actions") or []:
        if action.get("action_type") != ACTION_OWNERSHIP_CLAIM:
            continue
        if str(action.get("lane")) != lane:
            continue
        matches.append(action)
    if not matches:
        return None
    # Prefer agent-eligible RUNNABLE if present; else first match (fail later).
    for preferred in matches:
        if preferred.get("runnable_state") == "RUNNABLE" and preferred.get(
            "agent_eligible"
        ):
            return preferred
    return matches[0]


def list_claim_candidates(
    *,
    agent_id: str | None = None,
    frontier_matrix: dict | None = None,
    mission_control: dict | None = None,
    live: bool = False,
    repo: str | None = None,
    verifier_pool_path: str | Path | None = None,
    weights_path: str | Path | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """RO projection of F12 OWNERSHIP_CLAIM / steal candidates. Never mutates."""
    from atlas_dag import frontier_matrix as fm_mod

    matrix = frontier_matrix
    mc_fp = None
    frontier_fp = None
    notes: list[str] = ["reuse:atlas_dag.frontier_matrix.write_steal_candidates"]

    if mission_control is not None:
        mc_fp = mission_control.get("snapshot_fingerprint")
        frontier_fp = (mission_control.get("provenance") or {}).get(
            "frontier_fingerprint"
        ) or (mission_control.get("views") or {}).get("frontier", {}).get(
            "frontier_fingerprint"
        )

    if matrix is None and live and agent_id:
        from atlas_studio.mission_control import build_mission_control

        mc = build_mission_control(
            agent_id=agent_id,
            live=True,
            repo=repo,
            verifier_pool_path=verifier_pool_path,
            weights_path=weights_path,
            clock=clock,
        )
        mission_control = mc
        mc_fp = mc.get("snapshot_fingerprint")
        # Prefer nested matrix from live MC builder path when present.
        matrix = None
        # Rebuild frontier for the agent via the same live path MC uses.
        try:
            from atlas_dag import agents as agents_mod
            from atlas_dag import model as model_mod
            from atlas_dag import stack as stack_mod
            from atlas_dag.gh import GhClient

            client = GhClient(repo=repo) if repo else GhClient()
            snap = model_mod.build_snapshot(client)
            stacks = stack_mod.build_stacks(
                snap["nodes"], client, snap.get("main_branch") or "main"
            )
            registry = agents_mod.load_registry()
            matrix = fm_mod.build_frontier_matrix(
                snap,
                agent_id,
                registry,
                stacks=stacks,
                clock=clock,
            )
            notes.append("reuse:build_frontier_matrix")
            frontier_fp = matrix.get("frontier_fingerprint")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"LIVE_MATRIX_UNAVAILABLE:{type(exc).__name__}")
            matrix = {"actions": [], "agent": agent_id, "agent_status": "UNKNOWN"}

    if matrix is None:
        matrix = {"actions": [], "agent": agent_id, "agent_status": "UNKNOWN"}
        notes.append("MATRIX_ABSENT")

    if frontier_fp is None:
        frontier_fp = matrix.get("frontier_fingerprint")

    candidates = fm_mod.write_steal_candidates(matrix)
    # Also surface non-runnable OWNERSHIP_CLAIM rows for honesty (not eligible).
    all_claims = [
        a
        for a in (matrix.get("actions") or [])
        if a.get("action_type") == ACTION_OWNERSHIP_CLAIM
    ]
    if agent_id:
        # Agent binding happens in build_frontier_matrix; here we only refuse
        # to present a foreign agent's matrix as this agent's candidates.
        matrix_agent = matrix.get("agent")
        if matrix_agent and matrix_agent != agent_id:
            notes.append("AGENT_MATRIX_MISMATCH")
            candidates = []

    return {
        "schema": "ATLAS_STUDIO_CLAIM_CANDIDATES_V1",
        "generated_at_utc": clock(),
        "agent": agent_id or matrix.get("agent"),
        "agent_status": matrix.get("agent_status"),
        "candidates": candidates,
        "ownership_claim_actions": all_claims,
        "source_mc_fingerprint": mc_fp,
        "source_frontier_fingerprint": frontier_fp,
        "notes": notes,
        "honesty": {
            "requested_ne_claimed": True,
            "preview_ne_execution": True,
            "studio_ui_ne_authority": True,
            "attention_ne_authorization": True,
            "ranking_ne_authorization": True,
        },
    }


def preview_ownership_claim(
    *,
    agent_id: str,
    lane: str,
    frontier_matrix: dict | None = None,
    mission_control: dict | None = None,
    live: bool = False,
    repo: str | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict[str, Any]:
    """Build preview/why/impact from current truth. Never mutates; never emits."""
    lane_s, pr = parse_lane(lane)
    mc_fp = None
    frontier_fp = None
    matrix = frontier_matrix

    if mission_control is not None:
        mc_fp = mission_control.get("snapshot_fingerprint")
        frontier_fp = (mission_control.get("provenance") or {}).get(
            "frontier_fingerprint"
        )

    if matrix is None and live:
        listing = list_claim_candidates(
            agent_id=agent_id, live=True, repo=repo, clock=clock
        )
        # Re-fetch matrix via listing notes path is lossy; prefer injected.
        # For live without injection, rebuild briefly:
        try:
            from atlas_dag import agents as agents_mod
            from atlas_dag import frontier_matrix as fm_mod
            from atlas_dag import model as model_mod
            from atlas_dag import stack as stack_mod
            from atlas_dag.gh import GhClient

            client = GhClient(repo=repo) if repo else GhClient()
            snap = model_mod.build_snapshot(client)
            stacks = stack_mod.build_stacks(
                snap["nodes"], client, snap.get("main_branch") or "main"
            )
            registry = agents_mod.load_registry()
            matrix = fm_mod.build_frontier_matrix(
                snap, agent_id, registry, stacks=stacks, clock=clock
            )
            mc_fp = listing.get("source_mc_fingerprint") or mc_fp
            frontier_fp = matrix.get("frontier_fingerprint")
        except Exception as exc:  # noqa: BLE001
            return {
                "schema": SCHEMA_PREVIEW,
                "action_type": ACTION_OWNERSHIP_CLAIM,
                "preview_status": "UNKNOWN",
                "agent_id": agent_id,
                "target_lane": lane_s,
                "target_pr": pr,
                "target_head": None,
                "candidate_action_id": None,
                "runnable_state": None,
                "agent_eligible": None,
                "ownership": None,
                "owner": None,
                "why": [f"LIVE_TRUTH_UNAVAILABLE:{type(exc).__name__}"],
                "impact": [],
                "blockers": [f"LIVE_TRUTH_UNAVAILABLE:{type(exc).__name__}"],
                "source_mc_fingerprint": mc_fp,
                "source_frontier_fingerprint": frontier_fp,
                "generated_at_utc": clock(),
                "honesty": honesty_preview(),
            }

    if matrix is None:
        matrix = {"actions": []}

    if frontier_fp is None:
        frontier_fp = matrix.get("frontier_fingerprint")

    action = _find_claim_action(matrix, lane=lane_s, agent_id=agent_id)
    why: list[str] = []
    impact: list[str] = []
    blockers: list[str] = []

    if action is None:
        status = "CANDIDATE_ABSENT"
        why.append("NO_OWNERSHIP_CLAIM_ACTION_IN_FRONTIER")
        blockers.append("CANDIDATE_ABSENT")
        runnable = None
        eligible = None
        ownership = None
        owner = None
        head = None
        action_id = None
    else:
        runnable = action.get("runnable_state")
        eligible = bool(action.get("agent_eligible"))
        ownership = action.get("ownership")
        owner = action.get("owner")
        head = action.get("head")
        action_id = action.get("action_id")
        blockers = list(action.get("blocking_reasons") or [])
        if runnable == "RUNNABLE" and eligible:
            status = "CANDIDATE_ELIGIBLE"
            why.append("F12_OWNERSHIP_CLAIM_RUNNABLE_AND_AGENT_ELIGIBLE")
            why.append("LANE_UNOWNED_CLAIMABLE")
            impact.append("WOULD_POST_OWNER_CLAIMED_ON_DAG_BUS")
            impact.append("LANE_MUTEX_WOULD_BIND_TO_AGENT")
            impact.append("PREVIEW_DOES_NOT_MUTATE")
        else:
            status = "CANDIDATE_INELIGIBLE"
            why.append("F12_OWNERSHIP_CLAIM_NOT_RUNNABLE_OR_INELIGIBLE")
            if blockers:
                why.extend(f"BLOCKER:{b}" for b in blockers)

    why.append("PREVIEW_NE_EXECUTION")
    why.append("RANKING_NE_AUTHORIZATION")

    return {
        "schema": SCHEMA_PREVIEW,
        "action_type": ACTION_OWNERSHIP_CLAIM,
        "preview_status": status,
        "agent_id": agent_id,
        "target_lane": lane_s,
        "target_pr": pr,
        "target_head": head,
        "candidate_action_id": action_id,
        "runnable_state": runnable,
        "agent_eligible": eligible,
        "ownership": ownership,
        "owner": owner,
        "why": why,
        "impact": impact,
        "blockers": blockers,
        "source_mc_fingerprint": mc_fp,
        "source_frontier_fingerprint": frontier_fp,
        "generated_at_utc": clock(),
        "honesty": honesty_preview(),
    }


def build_ownership_claim_intent(
    *,
    agent_id: str,
    lane: str,
    source_mc_fingerprint: str,
    source_frontier_fingerprint: str | None = None,
    candidate_action_id: str | None = None,
    target_head: str | None = None,
    target_agent_id: str | None = None,
    capability_claims: list[str] | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    notes: str | None = None,
    clock: Callable[[], str] = utcnow,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Typed intent bound to fingerprints/ids. No authorization fields."""
    if extra_fields:
        bad = _reject_authz_fields(extra_fields)
        if bad:
            raise GovernedClaimError(";".join(bad))
    lane_s, pr = parse_lane(lane)
    target = target_agent_id or agent_id
    caps = list(
        capability_claims
        if capability_claims is not None
        else ["CLAIM_OWNERSHIP", "POST_EVENTS"]
    )
    requested_at = clock()
    material = {
        "action_type": ACTION_OWNERSHIP_CLAIM,
        "actor_agent_id": agent_id,
        "target_agent_id": target,
        "target_lane": lane_s,
        "target_pr": pr,
        "target_head": target_head,
        "source_mc_fingerprint": source_mc_fingerprint,
        "source_frontier_fingerprint": source_frontier_fingerprint,
        "candidate_action_id": candidate_action_id,
        "requested_at_utc": requested_at,
        "max_age_seconds": int(max_age_seconds),
        "capability_claims": caps,
    }
    intent_id = f"intent-ownership-claim-{_canonical_sha256(material)[:24]}"
    intent: dict[str, Any] = {
        "schema": SCHEMA_INTENT,
        "intent_id": intent_id,
        **material,
        "notes": notes,
        "honesty": honesty_intent(),
    }
    errors = validate_intent(intent)
    if errors:
        raise GovernedClaimError(f"REFUSED_SCHEMA:{errors[0]}")
    return intent


def evaluate_ownership_claim_intent(
    intent: dict[str, Any],
    *,
    frontier_matrix: dict | None = None,
    mission_control: dict | None = None,
    registry: Any | None = None,
    clock: Callable[[], str] = utcnow,
    now_clock: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Revalidate intent against live (or injected) truth. Never mutates."""
    now_fn = now_clock or clock
    now_s = now_fn()
    intent_id = intent.get("intent_id") if isinstance(intent, dict) else None

    if not isinstance(intent, dict):
        return _decision(
            REFUSED_SCHEMA,
            intent_id=None,
            reasons=["INTENT_NOT_OBJECT"],
            clock=now_fn,
        )

    authz_errs = _reject_authz_fields(intent)
    schema_errs = validate_intent(intent) if not authz_errs else authz_errs
    # validate_intent already includes authz; if authz-only early:
    if authz_errs:
        return _decision(
            REFUSED_SCHEMA,
            intent_id=intent_id,
            reasons=authz_errs,
            evidence={"schema_errors": authz_errs},
            clock=now_fn,
        )
    if schema_errs:
        return _decision(
            REFUSED_SCHEMA,
            intent_id=intent_id,
            reasons=["SCHEMA_INVALID", *schema_errs[:5]],
            evidence={"schema_errors": schema_errs[:10]},
            clock=now_fn,
        )

    if intent.get("action_type") != ACTION_OWNERSHIP_CLAIM:
        return _decision(
            REFUSED_SCHEMA,
            intent_id=intent_id,
            reasons=[f"UNSUPPORTED_ACTION_TYPE:{intent.get('action_type')}"],
            clock=now_fn,
        )

    actor = str(intent["actor_agent_id"])
    target_agent = str(intent["target_agent_id"])
    lane = str(intent["target_lane"])
    pr = int(intent["target_pr"])
    try:
        lane_s, pr_parsed = parse_lane(lane)
    except GovernedClaimError as exc:
        return _decision(
            REFUSED_TARGET_MISMATCH,
            intent_id=intent_id,
            reasons=[str(exc)],
            clock=now_fn,
        )
    if lane_s != lane or pr_parsed != pr:
        return _decision(
            REFUSED_TARGET_MISMATCH,
            intent_id=intent_id,
            reasons=["LANE_PR_INCONSISTENT"],
            clock=now_fn,
        )

    if actor != target_agent:
        # First WP: claim-for-self only (no foreign claim-as).
        return _decision(
            REFUSED_TARGET_MISMATCH,
            intent_id=intent_id,
            reasons=["ACTOR_TARGET_AGENT_MISMATCH"],
            clock=now_fn,
        )

    # Freshness: max_age
    try:
        requested = _parse_utc(str(intent["requested_at_utc"]))
        max_age = int(intent["max_age_seconds"])
        now_dt = _parse_utc(now_s)
        if now_dt - requested > timedelta(seconds=max_age):
            return _decision(
                REFUSED_STALE,
                intent_id=intent_id,
                reasons=["INTENT_MAX_AGE_EXCEEDED"],
                evidence={
                    "requested_at_utc": intent["requested_at_utc"],
                    "evaluated_at_utc": now_s,
                    "max_age_seconds": max_age,
                },
                clock=now_fn,
            )
    except (TypeError, ValueError) as exc:
        return _decision(
            REFUSED_SCHEMA,
            intent_id=intent_id,
            reasons=[f"TIMESTAMP_INVALID:{exc}"],
            clock=now_fn,
        )

    # Fingerprint freshness against live MC when provided.
    live_mc_fp = None
    live_frontier_fp = None
    if mission_control is not None:
        live_mc_fp = mission_control.get("snapshot_fingerprint")
        live_frontier_fp = (mission_control.get("provenance") or {}).get(
            "frontier_fingerprint"
        )
        if live_mc_fp and live_mc_fp != intent.get("source_mc_fingerprint"):
            return _decision(
                REFUSED_STALE,
                intent_id=intent_id,
                reasons=["SOURCE_MC_FINGERPRINT_MISMATCH"],
                evidence={
                    "intent_mc_fp": intent.get("source_mc_fingerprint"),
                    "live_mc_fp": live_mc_fp,
                },
                clock=now_fn,
            )
        intent_ff = intent.get("source_frontier_fingerprint")
        if intent_ff and live_frontier_fp and intent_ff != live_frontier_fp:
            return _decision(
                REFUSED_STALE,
                intent_id=intent_id,
                reasons=["SOURCE_FRONTIER_FINGERPRINT_MISMATCH"],
                evidence={
                    "intent_frontier_fp": intent_ff,
                    "live_frontier_fp": live_frontier_fp,
                },
                clock=now_fn,
            )

    matrix = frontier_matrix
    if matrix is None and mission_control is not None:
        # MC may embed frontier view without full actions; require explicit matrix.
        matrix = None

    if matrix is None:
        return _decision(
            REFUSED_POLICY,
            intent_id=intent_id,
            reasons=["LIVE_FRONTIER_MATRIX_REQUIRED"],
            clock=now_fn,
        )

    matrix_agent = matrix.get("agent")
    if matrix_agent and matrix_agent != actor:
        return _decision(
            REFUSED_AGENT_INVALID,
            intent_id=intent_id,
            reasons=["AGENT_MATRIX_MISMATCH"],
            evidence={"matrix_agent": matrix_agent, "actor": actor},
            clock=now_fn,
        )

    # Agent registry checks.
    if registry is not None:
        from atlas_dag import agents as agents_mod

        resolved = agents_mod.resolve_agent(registry, actor)
        if resolved.status != "REGISTERED":
            return _decision(
                REFUSED_AGENT_INVALID,
                intent_id=intent_id,
                reasons=[f"AGENT_NOT_REGISTERED:{resolved.status}"],
                clock=now_fn,
            )
        profile = resolved.profile or {}
        if not profile.get("active", False):
            return _decision(
                REFUSED_AGENT_INVALID,
                intent_id=intent_id,
                reasons=["AGENT_INACTIVE"],
                clock=now_fn,
            )
        caps = {str(c) for c in profile.get("capabilities", [])}
        if "CLAIM_OWNERSHIP" not in caps:
            return _decision(
                REFUSED_CAPABILITY,
                intent_id=intent_id,
                reasons=["CAPABILITY_MISSING:CLAIM_OWNERSHIP"],
                clock=now_fn,
            )
        if not (caps & {"WRITE_CODE", "WRITE_TESTS", "WRITE_DOCS"}):
            return _decision(
                REFUSED_CAPABILITY,
                intent_id=intent_id,
                reasons=["CAPABILITY_MISSING:WRITE"],
                clock=now_fn,
            )
        allowed_events = {str(e) for e in profile.get("event_permissions", [])}
        if "OWNER_CLAIMED" not in allowed_events:
            return _decision(
                REFUSED_CAPABILITY,
                intent_id=intent_id,
                reasons=["EVENT_NOT_PERMITTED:OWNER_CLAIMED"],
                clock=now_fn,
            )
        # Informational capability_claims must not invent grants; mismatch is policy.
        claimed = {str(c) for c in intent.get("capability_claims") or []}
        if claimed - caps:
            return _decision(
                REFUSED_CAPABILITY,
                intent_id=intent_id,
                reasons=["CAPABILITY_CLAIM_NOT_IN_REGISTRY"],
                evidence={"extra_claims": sorted(claimed - caps)},
                clock=now_fn,
            )
    else:
        return _decision(
            REFUSED_POLICY,
            intent_id=intent_id,
            reasons=["REGISTRY_REQUIRED_FOR_EVALUATION"],
            clock=now_fn,
        )

    action = _find_claim_action(matrix, lane=lane_s, agent_id=actor)
    if action is None:
        return _decision(
            REFUSED_NOT_RUNNABLE,
            intent_id=intent_id,
            reasons=["OWNERSHIP_CLAIM_ACTION_ABSENT"],
            clock=now_fn,
        )

    cand_id = intent.get("candidate_action_id")
    if cand_id and action.get("action_id") != cand_id:
        return _decision(
            REFUSED_TARGET_MISMATCH,
            intent_id=intent_id,
            reasons=["CANDIDATE_ACTION_ID_MISMATCH"],
            evidence={
                "intent_candidate": cand_id,
                "live_action_id": action.get("action_id"),
            },
            clock=now_fn,
        )

    if int(action.get("pr") or -1) != pr or str(action.get("lane")) != lane_s:
        return _decision(
            REFUSED_TARGET_MISMATCH,
            intent_id=intent_id,
            reasons=["LIVE_ACTION_TARGET_MISMATCH"],
            clock=now_fn,
        )

    intent_head = intent.get("target_head")
    live_head = action.get("head")
    if intent_head and live_head and intent_head != live_head:
        return _decision(
            REFUSED_STALE,
            intent_id=intent_id,
            reasons=["TARGET_HEAD_MOVED"],
            evidence={"intent_head": intent_head, "live_head": live_head},
            clock=now_fn,
        )

    ownership = action.get("ownership")
    owner = action.get("owner")
    if ownership == "OWNED" and owner == actor:
        return _decision(
            REFUSED_IDEMPOTENT_ALREADY_CLAIMED,
            intent_id=intent_id,
            reasons=["ALREADY_OWNED_BY_TARGET_AGENT"],
            evidence={"owner": owner, "lane": lane_s},
            clock=now_fn,
        )
    if ownership == "OWNED" and owner and owner != actor:
        return _decision(
            REFUSED_ALREADY_OWNED,
            intent_id=intent_id,
            reasons=[f"OWNERSHIP_MUTEX_HELD_BY:{owner}"],
            evidence={"owner": owner, "lane": lane_s},
            clock=now_fn,
        )
    if ownership == "AMBIGUOUS":
        return _decision(
            REFUSED_POLICY,
            intent_id=intent_id,
            reasons=["OWNERSHIP_AMBIGUOUS_FAIL_CLOSED"],
            clock=now_fn,
        )

    if action.get("frozen"):
        return _decision(
            REFUSED_POLICY,
            intent_id=intent_id,
            reasons=["LANE_FROZEN_BY_REPOSITORY_TRUTH"],
            clock=now_fn,
        )

    runnable = action.get("runnable_state")
    eligible = bool(action.get("agent_eligible"))
    if runnable != "RUNNABLE" or not eligible:
        # Ranking / presence alone never authorizes.
        return _decision(
            REFUSED_NOT_RUNNABLE,
            intent_id=intent_id,
            reasons=[
                f"RUNNABLE_STATE:{runnable}",
                f"AGENT_ELIGIBLE:{eligible}",
                *list(action.get("blocking_reasons") or [])[:5],
            ],
            evidence={
                "action_id": action.get("action_id"),
                "runnable_state": runnable,
                "agent_eligible": eligible,
            },
            clock=now_fn,
        )

    return _decision(
        EXECUTE_ALLOWED,
        intent_id=intent_id,
        reasons=["EVALUATION_PASSED"],
        evidence={
            "action_id": action.get("action_id"),
            "lane": lane_s,
            "pr": pr,
            "head": live_head,
            "source_mc_fingerprint": intent.get("source_mc_fingerprint"),
            "live_mc_fingerprint": live_mc_fp,
            "source_frontier_fingerprint": intent.get("source_frontier_fingerprint"),
            "live_frontier_fingerprint": live_frontier_fp
            or matrix.get("frontier_fingerprint"),
        },
        mutated=False,
        clock=now_fn,
    )


def execute_ownership_claim(
    intent: dict[str, Any],
    *,
    client: Any,
    registry: Any,
    frontier_matrix: dict | None = None,
    mission_control: dict | None = None,
    dry_run: bool = False,
    clock: Callable[[], str] = utcnow,
    now_clock: Callable[[], str] | None = None,
    emit_event: Callable[..., str] | None = None,
    expected_repo: str | None = None,
) -> dict[str, Any]:
    """Evaluate on fresh truth; emit OWNER_CLAIMED only when EXECUTE allowed.

    Routes through ``atlas_studio.governance.execute_governed_intent`` so claim
    is an instance of the reusable substrate (not a Studio mutation shortcut).
    dry_run=True never posts. Uses atlas_dag.emitter — does not reimplement
    ownership mutex.
    """
    from atlas_studio import governance as gov

    return gov.execute_governed_intent(
        intent,
        dry_run=dry_run,
        client=client,
        registry=registry,
        frontier_matrix=frontier_matrix,
        mission_control=mission_control,
        clock=clock,
        now_clock=now_clock,
        emit_event=emit_event,
        expected_repo=expected_repo,
    )


def _emit_ownership_claim(
    intent: dict[str, Any],
    decision: dict[str, Any],
    *,
    client: Any,
    registry: Any,
    frontier_matrix: dict | None = None,
    mission_control: dict | None = None,
    clock: Callable[[], str] = utcnow,
    now_clock: Callable[[], str] | None = None,
    emit_event: Callable[..., str] | None = None,
    expected_repo: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Authoritative mutate step for OWNERSHIP_CLAIM (emitter only)."""
    from atlas_dag import agents as agents_mod
    from atlas_dag import emitter as emitter_mod

    intent_id = intent.get("intent_id")
    actor = str(intent["actor_agent_id"])
    pr = int(intent["target_pr"])
    expect_head = intent.get("target_head")

    # Fail closed: a mutation must be pinned to an explicit repository
    # identity. Empty / whitespace is not a pin; GhClient auto-resolution
    # is not authority.
    pinned_repo = expected_repo.strip() if isinstance(expected_repo, str) else ""
    if not pinned_repo:
        return _decision(
            REFUSED_POLICY,
            intent_id=intent_id,
            reasons=["EXPECTED_REPO_REQUIRED_AT_EXECUTE"],
            evidence={
                "client_repo": getattr(client, "repo", None),
                "expected_repo_raw": expected_repo,
            },
            clock=now_clock or clock,
        )
    expected_repo = pinned_repo

    resolved = agents_mod.resolve_agent(registry, actor)
    profile = resolved.profile or {}
    try:
        ctx = emitter_mod.resolve_context(
            client, pr, profile, expected_repo=expected_repo
        )
        if expect_head is not None and ctx.head != expect_head:
            return _decision(
                REFUSED_STALE,
                intent_id=intent_id,
                reasons=["EXPECT_HEAD_MISMATCH_AT_EXECUTE"],
                evidence={"expect_head": expect_head, "resolved_head": ctx.head},
                clock=now_clock or clock,
            )
        # Permission re-check at emit boundary (control plane).
        owner = None
        action = _find_claim_action(
            frontier_matrix, lane=str(intent["target_lane"]), agent_id=actor
        )
        if action and action.get("ownership") == "OWNED":
            owner = action.get("owner")
        checks = emitter_mod.check_emit_permission(
            registry, actor, "OWNER_CLAIMED", owner
        )
        if not checks.ok:
            mapped = REFUSED_CAPABILITY
            joined = " ".join(checks.reasons)
            if "OWNERSHIP_MUTEX" in joined:
                mapped = REFUSED_ALREADY_OWNED
            elif "AGENT_" in joined:
                mapped = REFUSED_AGENT_INVALID
            return _decision(
                mapped,
                intent_id=intent_id,
                reasons=list(checks.reasons),
                clock=now_clock or clock,
            )
        payload = emitter_mod.build_event(
            ctx,
            event="OWNER_CLAIMED",
            state="CLAIMED",
            note=f"AS-STUDIO-A2-001 governed claim intent={intent_id}",
            next_actions=["ci"],
            expect_head=expect_head,
            utc=(now_clock or clock)(),
        )
        emit_fn = emit_event or emitter_mod.emit_event
        status = emit_fn(client, registry, payload, dry_run=False)
    except emitter_mod.EmitError as exc:
        msg = str(exc)
        code = REFUSED_POLICY
        if "EXPECT_HEAD" in msg or "HEAD_MOVED" in msg:
            code = REFUSED_STALE
        return _decision(
            code,
            intent_id=intent_id,
            reasons=[msg],
            clock=now_clock or clock,
        )

    mutated = status == "posted"
    reasons = ["EMITTED_OWNER_CLAIMED"]
    if status == "already-present":
        # Idempotent bus duplicate — not a second mutex claim mutation.
        reasons = ["EMIT_ALREADY_PRESENT_IDEMPOTENT"]
        return _decision(
            REFUSED_IDEMPOTENT_ALREADY_CLAIMED,
            intent_id=intent_id,
            reasons=reasons,
            evidence={
                "emit_status": status,
                "event_id": payload["event_id"],
                "evaluate_decision": EXECUTE_ALLOWED,
            },
            mutated=False,
            dry_run=False,
            emit_status=status,
            event_id=payload["event_id"],
            clock=now_clock or clock,
        )

    return _decision(
        EXECUTED,
        intent_id=intent_id,
        reasons=reasons,
        evidence={
            "emit_status": status,
            "event_id": payload["event_id"],
            "evaluate_decision": EXECUTE_ALLOWED,
            "lane": intent["target_lane"],
            "pr": pr,
            "substrate": "atlas_studio.governance",
        },
        mutated=mutated,
        dry_run=False,
        emit_status=status,
        event_id=payload["event_id"],
        clock=now_clock or clock,
    )


class _OwnershipClaimHandler:
    """First registered governed action — instance of the A2 substrate."""

    action_type = ACTION_OWNERSHIP_CLAIM

    def evaluate(self, intent: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return evaluate_ownership_claim_intent(
            intent,
            frontier_matrix=kwargs.get("frontier_matrix"),
            mission_control=kwargs.get("mission_control"),
            registry=kwargs.get("registry"),
            clock=kwargs.get("clock") or utcnow,
            now_clock=kwargs.get("now_clock"),
        )

    def apply_authorized(
        self, intent: dict[str, Any], decision: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        return _emit_ownership_claim(intent, decision, **kwargs)


def _register_with_governance() -> None:
    from atlas_studio import governance as gov

    gov.register_action(
        _OwnershipClaimHandler(),
        notes="AS-STUDIO-A2-001 first governed action (OWNERSHIP_CLAIM)",
    )


_register_with_governance()
