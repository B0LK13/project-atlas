"""Deterministic frontier prioritization and scoring (FEATURE_10).

PRIORITY != AUTHORITY.

Pipeline (never inverted):

  LIVE DAG
  → authorization/safety filtering (FEATURE_02 router.evaluate_lane)
  → runnable frontier (RUNNABLE_WRITE / RUNNABLE_READONLY)
  → scoring
  → deterministic ranked frontier

Blocked / frozen / foreign-owned / capability-incompatible / restack-required
/ verifier-only lanes may be reported for visibility with a nominal score, but
never enter the executable ranked frontier. A READONLY score can never promote
itself into WRITE. Ownership remains a mutex, not a score factor that bypasses
authorization.

Weights are repository-backed (ATLAS_FRONTIER_WEIGHTS_V1), versioned, and
reviewable. Malformed weights fail closed to an explicit embedded safe default
(SAFE_DEFAULT_WEIGHTS) rather than inventing a third silent model.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import agents as agents_mod
from . import events as events_mod

SCHEMA_CONST = "ATLAS_FRONTIER_SCORE_V1"
SCORE_SCHEMA = "atlas_frontier_score_v1.schema.json"
WEIGHTS_SCHEMA = "atlas_frontier_weights_v1.schema.json"
WEIGHTS_CONST = "ATLAS_FRONTIER_WEIGHTS_V1"

# Mirror router action-class vocabulary without importing router at module
# load (avoids circular import: router → score → router).
ROUTE_WRITE = "RUNNABLE_WRITE"
ROUTE_READONLY = "RUNNABLE_READONLY"
NO_ROUTE = "NO_SAFE_ROUTE"

FACTOR_NAMES = (
    "severity",
    "trust_governance",
    "blocker_value",
    "critical_path",
    "starvation",
    "evidence_freshness",
    "readiness",
    "coordination_cost",
    "platform_fit",
    "parallelism",
    "postmerge_closure",
    "risk_penalty",
)

# Explicit embedded safe default — never silent invention. Used only when the
# repository weights file is absent or fails schema/semantic validation.
SAFE_DEFAULT_WEIGHTS: dict[str, Any] = {
    "schema": WEIGHTS_CONST,
    "weights_id": "atlas-frontier-weights-safe-default",
    "version": 1,
    "description": "Embedded fail-closed safe default (FEATURE_10).",
    "weights": {
        "severity": 40.0,
        "trust_governance": 25.0,
        "blocker_value": 30.0,
        "critical_path": 15.0,
        "starvation": 10.0,
        "evidence_freshness": 12.0,
        "readiness": 18.0,
        "coordination_cost": -12.0,
        "platform_fit": 8.0,
        "parallelism": 6.0,
        "postmerge_closure": 20.0,
        "risk_penalty": -25.0,
    },
    "caps": {
        "starvation_max_raw": 5.0,
        "blocker_children_max": 8,
        "coordination_depth_max": 6,
    },
    "tiebreak": ["action_class_rank", "total_desc", "pr_asc", "lane_asc"],
}

_CLASS_RANK = {
    ROUTE_WRITE: 0,
    ROUTE_READONLY: 1,
    "BLOCKED": 2,
}


class ScoreError(RuntimeError):
    """Fail-closed scoring failure."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_weights_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry" / "frontier_weights.json"


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_score(packet: dict) -> list[str]:
    validator = events_mod.validator_for(SCORE_SCHEMA)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def validate_weights(payload: dict) -> list[str]:
    validator = events_mod.validator_for(WEIGHTS_SCHEMA)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(payload)
    )


def load_weights(path: str | Path | None = None) -> tuple[dict, str]:
    """Load repository weights or the explicit embedded safe default.

    Returns (weights, source) where source is 'registry' or 'safe_default'.
    Malformed/missing files never invent a third model — they surface the
    embedded SAFE_DEFAULT_WEIGHTS and a source marker.
    """
    target = Path(path) if path is not None else default_weights_path()
    if not target.is_file():
        return dict(SAFE_DEFAULT_WEIGHTS), "safe_default:missing"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(SAFE_DEFAULT_WEIGHTS), "safe_default:unreadable"
    if not isinstance(payload, dict):
        return dict(SAFE_DEFAULT_WEIGHTS), "safe_default:not_object"
    errors = validate_weights(payload)
    if errors:
        return dict(SAFE_DEFAULT_WEIGHTS), "safe_default:schema_invalid"
    return payload, "registry"


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _severity_raw(node: dict) -> tuple[float, str]:
    explicit = str(node.get("priority_class") or node.get("severity") or "").upper()
    if explicit in ("P0", "CRITICAL"):
        return 1.0, f"priority_class={explicit}"
    if explicit in ("P1", "HIGH"):
        return 0.7, f"priority_class={explicit}"
    if explicit in ("P2", "MEDIUM"):
        return 0.4, f"priority_class={explicit}"
    if explicit in ("P3", "LOW", "COSMETIC"):
        return 0.1, f"priority_class={explicit}"
    reasons = list((node.get("gate") or {}).get("reasons") or [])
    if any(r.startswith("P0_") or r == "P0_OPEN" for r in reasons):
        return 1.0, "gate:P0_OPEN"
    if any(r.startswith("P1_") or r == "P1_OPEN" for r in reasons):
        return 0.7, "gate:P1_OPEN"
    hazard = str(node.get("hazard_class") or "")
    if hazard == "C_HUMAN_CHECKPOINT":
        return 0.6, "hazard_class=C_HUMAN_CHECKPOINT"
    if hazard == "B_DISPOSABLE_ONLY":
        return 0.3, "hazard_class=B_DISPOSABLE_ONLY"
    return 0.2, "default_baseline"


def _factor(raw: float, weight: float, rationale: str) -> dict:
    return {
        "raw": round(float(raw), 6),
        "weight": float(weight),
        "weighted": round(float(raw) * float(weight), 6),
        "rationale": rationale,
    }


def compute_factors(node: dict, stack: dict | None, profile: dict | None,
                    weights: dict, *, now: datetime | None = None) -> dict[str, dict]:
    """Explainable raw+weighted contributions for one already-classified node."""
    w = weights["weights"]
    caps = weights["caps"]
    gate_reasons = list((node.get("gate") or {}).get("reasons") or [])
    waits = list(node.get("waiting_on") or [])
    children = list((stack or {}).get("children") or [])
    depth = (stack or {}).get("depth")
    if depth is None:
        depth = 0

    sev_raw, sev_why = _severity_raw(node)
    factors: dict[str, dict] = {
        "severity": _factor(sev_raw, w["severity"], sev_why),
    }

    trust = 0.0
    trust_bits: list[str] = []
    if "FORMAL_IV" in "".join(gate_reasons) or "IV" in waits:
        trust += 0.5
        trust_bits.append("iv_outstanding")
    if node.get("claim_integrity") != "PASS":
        trust += 0.3
        trust_bits.append("claim_not_pass")
    if any("POLICY" in r or "HUMAN_GATE" in r for r in gate_reasons):
        trust += 0.4
        trust_bits.append("policy_or_human_gate")
    factors["trust_governance"] = _factor(
        min(1.0, trust), w["trust_governance"],
        ",".join(trust_bits) or "no_governance_pressure")

    child_count = min(len(children), int(caps["blocker_children_max"]))
    # Downstream unblock value: more dependents ⇒ higher blocker value.
    blocker_raw = child_count / max(int(caps["blocker_children_max"]), 1)
    factors["blocker_value"] = _factor(
        blocker_raw, w["blocker_value"],
        f"children={len(children)} capped={child_count}")

    # Critical path: prefer current roots/shallow work that unlocks stacks.
    if (stack or {}).get("restack_required") or \
            (stack or {}).get("stack_state") in (
                "RESTACK_REQUIRED", "PARENT_MOVED", "PARENT_MISSING_OR_UNKNOWN",
                "CYCLE_INVALID", "ANCESTRY_UNKNOWN", "AMBIGUOUS"):
        crit = 0.0
        crit_why = f"stack_not_current:{(stack or {}).get('stack_state')}"
    elif depth == 0:
        crit = 1.0 if children else 0.5
        crit_why = "stack_root"
    else:
        crit = max(0.0, 1.0 - (float(depth) / max(int(caps["coordination_depth_max"]), 1)))
        crit_why = f"depth={depth}"
    factors["critical_path"] = _factor(crit, w["critical_path"], crit_why)

    # Starvation: material age vs snapshot clock when opened_at_utc present;
    # otherwise PR number proxy (lower PR ⇒ older ⇒ mild boost), capped.
    age_raw = 0.0
    age_why = "no_age_signal"
    opened = _parse_iso(node.get("opened_at_utc"))
    if opened is not None and now is not None:
        hours = max(0.0, (now - opened).total_seconds() / 3600.0)
        age_raw = min(hours / 168.0, float(caps["starvation_max_raw"]))  # weekly scale
        age_why = f"opened_age_hours={hours:.2f}"
    elif isinstance(node.get("pr"), int):
        # Stable proxy only: invert within a bounded band so starvation never
        # overwhelms severity (cap applied).
        age_raw = min(float(caps["starvation_max_raw"]),
                      max(0.0, (10_000 - int(node["pr"])) / 10_000.0))
        age_why = f"pr_proxy={node['pr']}"
    factors["starvation"] = _factor(age_raw, w["starvation"], age_why)

    fresh = 0.0
    fresh_bits: list[str] = []
    if node.get("ci_status") == "PASS":
        fresh += 0.6
        fresh_bits.append("ci_pass")
    elif node.get("ci_status") in (None, "UNKNOWN", "PENDING", "RUNNING"):
        fresh += 0.1
        fresh_bits.append(f"ci={node.get('ci_status')}")
    if node.get("formal_iv"):
        fresh += 0.4
        fresh_bits.append("formal_iv_present")
    factors["evidence_freshness"] = _factor(
        min(1.0, fresh), w["evidence_freshness"],
        ",".join(fresh_bits) or "no_fresh_evidence")

    ready = 1.0
    ready_bits: list[str] = []
    for wait in waits:
        ready -= 0.15
        ready_bits.append(f"waiting:{wait}")
    if node.get("draft"):
        ready -= 0.3
        ready_bits.append("draft")
    ready = max(0.0, ready)
    factors["readiness"] = _factor(
        ready, w["readiness"], ",".join(ready_bits) or "ready_baseline")

    # Coordination cost is a positive raw count scaled by a negative weight.
    cost_raw = min(float(depth), float(caps["coordination_depth_max"])) / max(
        float(caps["coordination_depth_max"]), 1.0)
    if len(waits) > 3:
        cost_raw = min(1.0, cost_raw + 0.2)
    factors["coordination_cost"] = _factor(
        cost_raw, w["coordination_cost"], f"depth={depth};waits={len(waits)}")

    fit = 0.0
    fit_why = "no_profile"
    if profile is not None:
        platforms = {str(p) for p in profile.get("platforms", [])}
        reqs = set(map(str, node.get("platform_requirements") or []))
        if not reqs or (reqs & (platforms | {"any"})):
            fit = 1.0
            fit_why = "platform_compatible"
        else:
            fit = 0.0
            fit_why = "platform_mismatch_should_be_blocked"
    factors["platform_fit"] = _factor(fit, w["platform_fit"], fit_why)

    # Parallelism: unowned runnable work can be claimed; owned-by-self is fine
    # but offers less parallelism opportunity for the fleet.
    para = 0.0
    para_why = "none"
    if node.get("ownership") == "UNOWNED":
        para = 1.0
        para_why = "unowned_claimable"
    elif node.get("owner") and profile and node.get("owner") == profile.get("agent_id"):
        para = 0.4
        para_why = "owned_by_self"
    factors["parallelism"] = _factor(para, w["parallelism"], para_why)

    post = 0.0
    post_why = "not_postmerge"
    if node.get("state") == "MERGED_UNSEALED" or node.get("postmerge_seal_value"):
        post = float(node.get("postmerge_seal_value") or 1.0)
        post_why = "postmerge_closure_value"
    elif str(node.get("priority_class") or "").upper() == "POSTMERGE":
        post = 0.8
        post_why = "priority_class=POSTMERGE"
    factors["postmerge_closure"] = _factor(min(1.0, post), w["postmerge_closure"], post_why)

    risk = 0.0
    risk_bits: list[str] = []
    if node.get("ownership") == "AMBIGUOUS":
        risk += 1.0
        risk_bits.append("ownership_ambiguous")
    if not node.get("tree"):
        risk += 0.4
        risk_bits.append("tree_unknown")
    if (stack or {}).get("stack_state") == "ANCESTRY_UNKNOWN":
        risk += 0.5
        risk_bits.append("ancestry_unknown")
    if node.get("ci_status") == "FAILURE":
        risk += 0.3
        risk_bits.append("ci_failure")
    if node.get("uncertainty"):
        risk += min(0.5, 0.1 * len(node.get("uncertainty") or []))
        risk_bits.append("node_uncertainty")
    factors["risk_penalty"] = _factor(
        min(1.0, risk), w["risk_penalty"],
        ",".join(risk_bits) or "no_risk_signals")

    # Stable factor key order.
    return {name: factors[name] for name in FACTOR_NAMES}


def _total(factors: dict[str, dict]) -> float:
    return round(sum(f["weighted"] for f in factors.values()), 6)


def _tiebreak_key(entry_class: str, total: float, pr: int, lane: str,
                  order: list[str]) -> list:
    key: list[Any] = []
    for item in order:
        if item == "action_class_rank":
            key.append(_CLASS_RANK.get(entry_class, 9))
        elif item == "total_desc":
            key.append(-total)
        elif item == "pr_asc":
            key.append(int(pr))
        elif item == "lane_asc":
            key.append(str(lane))
    return key


def score_node(node: dict, auth: dict, stack: dict | None, profile: dict | None,
               weights: dict, *, now: datetime | None = None) -> dict:
    """Score one node after authorization. Never alters action_class."""
    factors = compute_factors(node, stack, profile, weights, now=now)
    total = _total(factors)
    action = auth["action_class"]
    pr = int(node["pr"])
    lane = str(node.get("lane") or f"pr/{pr}")
    if action == NO_ROUTE or not auth.get("routable"):
        return {
            "pr": pr,
            "lane": lane,
            "action_class": "BLOCKED",
            "executable": False,
            "nominal_total": total,
            "factors": factors,
            "authorization": {
                "routable": False,
                "action_class": action,
                "reasons": list(auth.get("reasons") or []),
                "blockers": list(auth.get("blockers") or []),
            },
        }
    # READONLY can never outrank itself into WRITE — action_class is auth truth.
    return {
        "pr": pr,
        "lane": lane,
        "action_class": action,
        "executable": True,
        "total": total,
        "factors": factors,
        "tiebreak_key": _tiebreak_key(
            action, total, pr, lane, list(weights["tiebreak"])),
        "authorization": {
            "routable": True,
            "action_class": action,
            "reasons": list(auth.get("reasons") or []),
            "blockers": list(auth.get("blockers") or []),
        },
    }


def rank_frontier(
    snapshot: dict,
    *,
    agent_id: str | None = None,
    registry: agents_mod.RegistryResult | None = None,
    stacks: dict | None = None,
    weights: dict | None = None,
    weights_source: str = "explicit",
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Authorize first, then score, then deterministically rank.

    Without an agent, every node is scored for visibility but only snapshot
    RUNNABLE_* states enter the executable ranked list (as READONLY floor);
    WRITE still requires ownership classification from the snapshot plus a
    concrete agent via router semantics — so agent-less ranking never grants
    write authority.
    """
    cfg = weights if weights is not None else SAFE_DEFAULT_WEIGHTS
    if weights is None:
        weights_source = "safe_default:inline"
    now = _parse_iso(clock())

    profile: dict | None = None
    agent_status = "NONE"
    if agent_id is not None:
        if registry is None:
            raise ScoreError("REGISTRY_REQUIRED_FOR_AGENT_SCORING")
        resolved = agents_mod.resolve_agent(registry, agent_id)
        agent_status = resolved.status
        if resolved.status != "REGISTERED":
            packet = {
                "schema": SCHEMA_CONST,
                "generated_at_utc": clock(),
                "weights_id": cfg["weights_id"],
                "weights_version": int(cfg["version"]),
                "weights_source": weights_source,
                "agent": agent_id,
                "agent_status": agent_status,
                "ranked": [],
                "blocked": [],
                "ranking_fingerprint": _canonical_sha256(
                    {"agent": agent_id, "status": agent_status, "ranked": []}),
                "provenance": _provenance(),
            }
            return packet
        profile = resolved.profile or {}
        if not profile.get("active", False):
            agent_status = "REGISTERED_INACTIVE"
            packet = {
                "schema": SCHEMA_CONST,
                "generated_at_utc": clock(),
                "weights_id": cfg["weights_id"],
                "weights_version": int(cfg["version"]),
                "weights_source": weights_source,
                "agent": agent_id,
                "agent_status": agent_status,
                "ranked": [],
                "blocked": [],
                "ranking_fingerprint": _canonical_sha256(
                    {"agent": agent_id, "status": agent_status, "ranked": []}),
                "provenance": _provenance(),
            }
            return packet
        agent_status = "REGISTERED_ACTIVE"

    # Authorization before scoring: evaluate every node, never score-first.
    nodes = list(snapshot.get("nodes") or [])
    ranked: list[dict] = []
    blocked: list[dict] = []
    for node in nodes:
        lane = str(node.get("lane") or "")
        stack = (stacks or {}).get(lane)
        if profile is not None:
            from . import router as router_mod
            auth = router_mod.evaluate_lane(profile, node, stack)
        else:
            # Agent-less visibility: snapshot state only; never invent WRITE.
            state = node.get("state")
            if state in (ROUTE_WRITE, ROUTE_READONLY):
                auth = {
                    "lane": lane,
                    "action_class": ROUTE_READONLY,
                    "routable": True,
                    "reasons": ["AGENTLESS_VISIBILITY_READONLY_FLOOR"],
                    "blockers": ["NO_AGENT_FOR_WRITE_AUTHORIZATION"]
                    if state == ROUTE_WRITE else [],
                }
            else:
                auth = {
                    "lane": lane,
                    "action_class": NO_ROUTE,
                    "routable": False,
                    "reasons": [],
                    "blockers": [f"SNAPSHOT_STATE_NOT_RUNNABLE:{state}"],
                }
        entry = score_node(node, auth, stack, profile, cfg, now=now)
        if entry["executable"]:
            ranked.append(entry)
        else:
            blocked.append(entry)

    ranked.sort(key=lambda e: tuple(e["tiebreak_key"]))
    blocked.sort(key=lambda e: (-e["nominal_total"], e["pr"], e["lane"]))

    material = {
        "weights_id": cfg["weights_id"],
        "weights_version": int(cfg["version"]),
        "agent": agent_id,
        "ranked": [
            {"pr": e["pr"], "lane": e["lane"], "action_class": e["action_class"],
             "total": e["total"], "factors": e["factors"]}
            for e in ranked
        ],
        "blocked": [
            {"pr": e["pr"], "lane": e["lane"], "nominal_total": e["nominal_total"],
             "blockers": e["authorization"]["blockers"]}
            for e in blocked
        ],
    }
    packet = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "weights_id": cfg["weights_id"],
        "weights_version": int(cfg["version"]),
        "weights_source": weights_source,
        "agent": agent_id,
        "agent_status": agent_status,
        "ranked": ranked,
        "blocked": blocked,
        "ranking_fingerprint": _canonical_sha256(material),
        "provenance": _provenance(),
    }
    return packet


def _provenance() -> dict:
    return {
        "generator": "atlas-dag frontier-score (FEATURE_10)",
        "authorization_before_scoring": True,
        "priority_is_not_authority": True,
        "truth_sources": [
            "ATLAS_DAG_SNAPSHOT_V1",
            "FEATURE_01 agent registry",
            "FEATURE_02 router authorization",
            "FEATURE_03 stack topology",
            "FEATURE_05 verifier pool (via snapshot)",
            "FEATURE_07 evidence signals (via node ci/iv)",
            "FEATURE_09 post-merge closure hints",
            "ATLAS_FRONTIER_WEIGHTS_V1",
        ],
    }


def explain_priority(snapshot: dict, pr: int, **kwargs: Any) -> dict:
    """Explain one PR's score contributions (ranked or blocked)."""
    packet = rank_frontier(snapshot, **kwargs)
    for entry in packet["ranked"]:
        if entry["pr"] == pr:
            return {"schema": SCHEMA_CONST, "found": True, "entry": entry,
                    "packet_fingerprint": packet["ranking_fingerprint"]}
    for entry in packet["blocked"]:
        if entry["pr"] == pr:
            return {"schema": SCHEMA_CONST, "found": True, "entry": entry,
                    "packet_fingerprint": packet["ranking_fingerprint"]}
    return {"schema": SCHEMA_CONST, "found": False, "pr": pr,
            "reason": "PR_NOT_IN_SNAPSHOT"}


def apply_ranking_to_routes(routes: list[dict], score_packet: dict) -> list[dict]:
    """Reorder already-authorized router routes by FEATURE_10 scores.

    Routes that are not routable stay after executable ones; WRITE still
    precedes READONLY via action_class_rank inside tiebreak. Missing scores
    fall back to (class_rank, lane) — never invent authority.
    """
    by_lane = {e["lane"]: e for e in score_packet.get("ranked", [])}
    def key(route: dict) -> tuple:
        entry = by_lane.get(route["lane"])
        if entry is not None and route.get("routable"):
            return tuple(entry["tiebreak_key"])
        return (_CLASS_RANK.get(route["action_class"], 9), str(route.get("lane", "")))
    return sorted(routes, key=key)
