"""Automatic handoff packet generation (FEATURE_08, AUTOMATIC_HANDOFF_GENERATION).

A handoff packet is a PROJECTION of current DAG/repository/evidence truth —
never new authority. It is built exclusively by reusing the Features 1–7
resolvers (snapshot model, stack topology, verifier pool, dispatch planner,
evidence graph); this module adds no truth of its own.

Core rules:

- UNKNOWN preservation: any field whose truth cannot be resolved stays
  literal "UNKNOWN" (or null per field contract) with an explicit entry in
  the packet-level `uncertainty` list. UNKNOWN is never converted into
  PASS/FAIL by inference.
- TOCTOU guard: the candidate HEAD is re-resolved from live repository truth
  after the packet is built; any move => HandoffStale
  (HANDOFF_STALE_DURING_BUILD) and NO packet is emitted.
- Determinism: `truth_fingerprint` is a sha256 over the canonical JSON of
  the material identity/state fields only (generated_at_utc, handoff_id and
  the mode-specific `presentation` block are excluded), so equivalent
  snapshots yield identical fingerprints and identical handoff_ids.
- One canonical packet: mode (general / verifier / resume) only adds a
  `presentation` emphasis block; material fields are identical across modes.
- A prospective merge SHA never appears as a merge receipt: an open PR has
  merge_receipt.receipt = null with reason "PR_OPEN".
- CI state is exact-head only (model.ci_status_for_head semantics):
  predecessor-head runs can never surface as current CI.
- Invalidated / stale-proof evidence never appears in the reusable list;
  the evidence section exposes all five FEATURE_07 states per artifact.

Generation only: this module never posts, emails, or otherwise delivers.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import dispatch as dispatch_mod
from . import events as events_mod
from . import evidence as evidence_mod
from . import evidence_graph as evidence_graph_mod
from . import model as model_mod
from . import stack as stack_mod
from . import verifiers as verifiers_mod

SCHEMA_CONST = "ATLAS_HANDOFF_V1"
HANDOFF_SCHEMA = "atlas_handoff_v1.schema.json"

# Handoff modes (controlled vocabulary). Mode only shapes `presentation`.
MODES = ("general", "verifier", "resume")

# All five FEATURE_07 graph states, always present in the evidence summary.
GRAPH_STATES = (
    evidence_graph_mod.EXACT_CURRENT,
    evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE,
    evidence_graph_mod.PREDECESSOR_ONLY,
    evidence_graph_mod.INVALIDATED,
    evidence_graph_mod.UNKNOWN,
)

# Gate reasons that encode a validation requirement for a verifier audience.
_VALIDATION_PREFIXES = (
    "EXACT_HEAD_CI",
    "FORMAL_IV",
    "CLAIM_INTEGRITY",
    "MERGEABILITY",
    "P0_OPEN",
    "P1_OPEN",
)


class HandoffError(RuntimeError):
    """Fail-closed: the packet cannot be built truthfully."""


class HandoffStale(HandoffError):
    """HANDOFF_STALE_DURING_BUILD: live HEAD moved during packet build."""


class HandoffUnavailable(HandoffError):
    """The requested lane has no resolvable truth (e.g. UNKNOWN_PR)."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_packet(packet: dict) -> list[str]:
    """Schema-validation error summaries for one packet ([] = valid)."""
    validator = events_mod.validator_for(HANDOFF_SCHEMA)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _live_pr(client: Any, pr: int) -> dict | None:
    return next((p for p in client.open_prs() if p.get("number") == pr), None)


def _base_head(client: Any, base_branch: str | None) -> str | None:
    if not base_branch:
        return None
    try:
        base = client.branch_head(base_branch)
    except Exception:
        return None
    return base.get("sha") if base else None


def _receipt_verifier(client: Any, receipt_id: str) -> str | None:
    """Verifier id behind an eligible receipt id, from the #719 stream."""
    issue = client.dag_issue()
    if not issue:
        return None
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    for receipt in ingested.receipts:
        if receipt.get("receipt_id") == receipt_id:
            return receipt.get("verifier_id")
    return None


def _evidence_section(client: Any, pr: int, head: str | None, tree: str | None,
                      record: dict | None,
                      store: evidence_mod.EvidenceStore | None) -> dict:
    """All five FEATURE_07 states, per-artifact reasons, and a reusable list
    that can never contain invalidated / stale-proof artifacts."""
    states: dict[str, list[str]] = {state: [] for state in GRAPH_STATES}
    artifacts: list[dict] = []
    uncertainty: list[str] = []
    if store is not None:
        records = store.for_pr(pr)
        parent_head = record.get("parent_head") if record else None
        context = {
            "pr": pr,
            "current_head": head,
            "current_tree": tree,
            "current_parent_head": parent_head,
            "current_main_head": _safe_main_head(client),
            "changed_files": None,  # live diff truth stays unresolved here
            "current_platform": None,
            "current_test_set": None,
            "current_toolchain": None,
            "current_verifier_principal": None,
            "current_verifier_session": None,
            "equivalence_proofs": [],
        }
        graph = evidence_graph_mod.build_graph(records, context)
        for node in graph["nodes"]:
            states.setdefault(node["state"], []).append(node["evidence_id"])
            artifacts.append({
                "evidence_id": node["evidence_id"],
                "evidence_class": node["evidence_class"],
                "state": node["state"],
                "reasons": node["reasons"],
                "reuse_proof": node["reuse_proof"],
                "uncertainty": node["uncertainty"],
            })
        for state in states:
            states[state] = sorted(states[state])
        uncertainty.extend(graph["uncertainty"])
    reusable = sorted(
        states[evidence_graph_mod.EXACT_CURRENT]
        + states[evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE]
    )
    return {"states": states, "artifacts": artifacts, "reusable": reusable,
            "uncertainty": sorted(set(uncertainty))}


def _safe_main_head(client: Any) -> str | None:
    try:
        main_branch = client.default_branch()
        main = client.branch_head(main_branch) if main_branch else None
    except Exception:
        return None
    return main.get("sha") if main else None


def _pool_prohibitions(pool_path: Path) -> list[str]:
    """Sorted union of declared verifier prohibitions (the honest boundary of
    what a verifier must not do, from the pool file itself — never invented).
    An unavailable/invalid pool yields no prohibitions, never invented ones."""
    loaded = verifiers_mod.load_pool(pool_path)
    if not loaded.valid or loaded.pool is None:
        return []
    prohibitions: set[str] = set()
    for entry in loaded.pool.get("verifiers", []):
        prohibitions.update(str(p) for p in entry.get("prohibitions", []))
    return sorted(prohibitions)


def _presentation(mode: str, node: dict, stack_record: dict | None,
                  evidence_section: dict, gate_reasons: list[str],
                  prohibitions: list[str]) -> dict:
    """Mode-specific emphasis block. Presentation ONLY: every value here is
    derived from material truth already in the packet, never contradictory
    with it, and always excluded from the truth fingerprint."""
    if mode == "verifier":
        outstanding = sorted(
            artifact["evidence_id"]
            for artifact in evidence_section["artifacts"]
            if artifact["state"] in (evidence_graph_mod.PREDECESSOR_ONLY,
                                     evidence_graph_mod.INVALIDATED)
        )
        return {
            "audience": "verifier",
            "changed_scope_summary": outstanding,
            "outstanding_claims": sorted(gate_reasons),
            "validation_requirements": sorted(
                reason for reason in gate_reasons
                if reason.startswith(_VALIDATION_PREFIXES)
            ),
            "prohibited_verifier_actions": prohibitions,
        }
    if mode == "resume":
        next_actions = list(node.get("next_actions") or [])
        return {
            "audience": "resuming-agent",
            "next_safe_action": next_actions[0] if next_actions else "UNKNOWN",
            "topology": {
                "lane": node.get("lane"),
                "stack_state": (stack_record or {}).get("stack_state"),
                "depth": (stack_record or {}).get("depth"),
                "parent_pr": (stack_record or {}).get("parent_pr"),
            },
            "invalidated_evidence": sorted(
                evidence_section["states"][evidence_graph_mod.INVALIDATED]),
            "reusable_evidence": list(evidence_section["reusable"]),
        }
    return {"audience": "general"}


def build_handoff(
    pr_number: int,
    mode: str,
    client: Any,
    *,
    evidence_store: evidence_mod.EvidenceStore | None = None,
    registry: Any = None,
    verifier_pool: str | Path | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Build one ATLAS_HANDOFF_V1 packet from live Features 1–7 truth.

    Raises HandoffUnavailable when the lane is not truthfully resolvable and
    HandoffStale (HANDOFF_STALE_DURING_BUILD) when the candidate HEAD moves
    between the initial resolution and the final TOCTOU re-resolution; in
    both cases NO packet is emitted. `registry` is accepted for call-site
    symmetry with the dispatcher; handoff truth never depends on it.
    """
    del registry  # handoff is a pure truth projection; no registry authority
    if mode not in MODES:
        raise HandoffError(f"UNKNOWN_MODE:{mode}")

    pool_path = Path(verifier_pool) if verifier_pool is not None \
        else verifiers_mod.default_pool_path()
    snapshot = model_mod.build_snapshot(client, pool_path=pool_path)
    node = next((n for n in snapshot["nodes"] if n["pr"] == pr_number), None)
    if node is None:
        raise HandoffUnavailable(f"UNKNOWN_PR:{pr_number}")
    head = node.get("head")
    if not head:
        raise HandoffUnavailable(f"PR_HEAD_UNRESOLVED:{pr_number}")

    stacks = stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    stack_record = stacks.get(node["lane"]) or None

    issue = client.dag_issue()
    pool = verifiers_mod.resolve_pool(
        client.issue_body(issue["number"]) if issue else None,
        path=pool_path, repo=client.repo)

    gate = node["gate"]
    gate_reasons = list(gate.get("reasons") or [])

    # Formal IV: satisfied only by the snapshot's eligible receipt; the
    # verifier binding comes from the authenticated pool, never inferred.
    receipt_id = node.get("formal_iv")
    verifier_id: str | None = None
    verifier_binding: str | None = None
    if receipt_id:
        verifier_id = _receipt_verifier(client, receipt_id)
        if verifier_id is not None:
            verifier_binding = pool.bindings.get(verifier_id)

    base_branch = node.get("base")
    base_head = _base_head(client, base_branch)
    main_head = snapshot.get("main_head")

    ci = {"status": node["ci_status"], "run_id": node["ci_run_id"], "head": head}
    formal_iv = {
        "state": "SATISFIED" if receipt_id else "MISSING",
        "receipt_id": receipt_id,
        "verifier_id": verifier_id,
        "verifier_binding": verifier_binding,
    }
    mergeable = node.get("mergeable") or "UNKNOWN"
    merge_guardian = {"merge_gate": gate["merge_gate"], "reasons": gate_reasons}
    # A prospective merge SHA is never a merge receipt: the PR is open.
    merge_receipt = {"receipt": None, "reason": "PR_OPEN"}

    dispatch_plan: dict | None
    if node.get("frozen"):
        dispatch_plan = dispatch_mod.plan_dispatch(
            node, client, None, None, pool, evidence_store=evidence_store)
    else:
        dispatch_plan = node.get("dispatch")

    evidence_section = _evidence_section(
        client, pr_number, head, node.get("tree"), stack_record, evidence_store)

    # Gates: verbatim truth states, never an inferred PASS/FAIL conversion.
    if pool.pool_invalid:
        verifier_gate = "VERIFIER_POOL_INVALID"
    elif receipt_id:
        verifier_gate = "SATISFIED"
    elif pool.present and not pool.bindings:
        verifier_gate = "VERIFIER_IDENTITY_UNBOUND"
    else:
        verifier_gate = "MISSING"
    gates = {
        "owner": node["ownership"],
        "verifier": verifier_gate,
        "platform": str(mergeable),
        "policy": gate["merge_gate"],
    }

    blockers = list(node.get("blockers") or [])
    next_actions = list(node.get("next_actions") or [])

    stack_out: dict[str, Any] = {
        "root": None, "parent_pr": None, "parent_head": None,
        "depth": None, "stack_state": stack_mod.PARENT_MISSING,
        "restack_required": False, "target_branch": base_branch,
    }
    if stack_record is not None:
        stack_out.update({
            "root": stack_record.get("stack_root"),
            "parent_pr": stack_record.get("parent_pr"),
            "parent_head": stack_record.get("parent_head"),
            "depth": stack_record.get("depth"),
            "stack_state": stack_record.get("stack_state"),
            "restack_required": bool(stack_record.get("restack_required")),
            "target_branch": stack_record.get("target_branch"),
        })

    # UNKNOWN preservation: explicit uncertainty for everything unresolved.
    uncertainty: set[str] = set(evidence_section["uncertainty"])
    if not node.get("tree"):
        uncertainty.add("TREE_UNKNOWN")
    if not base_head:
        uncertainty.add("BASE_HEAD_UNKNOWN")
    if not main_head:
        uncertainty.add("MAIN_HEAD_UNKNOWN")
    if node.get("owner") is None:
        uncertainty.add("OWNER_UNKNOWN")
    if receipt_id and verifier_binding is None:
        uncertainty.add("VERIFIER_BINDING_UNKNOWN")
    if mergeable == "UNKNOWN":
        uncertainty.add("MERGEABILITY_UNKNOWN")

    material = {
        "pr": pr_number,
        "head": head,
        "tree": node.get("tree"),
        "base_branch": base_branch,
        "base_head": base_head,
        "main_head": main_head,
        "stack": stack_out,
        "owner": node.get("owner"),
        "ownership": node["ownership"],
        "claimants": sorted(node.get("claimants") or []),
        "frozen": bool(node.get("frozen")),
        "ci": ci,
        "formal_iv": formal_iv,
        "claim_integrity": node.get("claim_integrity"),
        "mergeable": mergeable,
        "merge_guardian": merge_guardian,
        "merge_receipt": merge_receipt,
        "blockers": blockers,
        "dispatch": dispatch_plan,
        "evidence": evidence_section,
        "next_actions": next_actions,
        "gates": gates,
    }
    fingerprint = _canonical_sha256(material)
    handoff_id = "handoff-" + hashlib.sha256(
        f"{fingerprint}|{pr_number}|{mode}".encode("utf-8")).hexdigest()[:16]

    packet = {
        "schema": SCHEMA_CONST,
        "handoff_id": handoff_id,
        "generated_at_utc": clock(),
        "mode": mode,
        "repo": client.repo or model_mod.UNKNOWN,
        "pr": pr_number,
        "head": head,
        "tree": node.get("tree"),
        "truth_fingerprint": fingerprint,
        "base_branch": base_branch,
        "base_head": base_head,
        "main_head": main_head,
        "stack": stack_out,
        "owner": node.get("owner"),
        "ownership": node["ownership"],
        "claimants": sorted(node.get("claimants") or []),
        "frozen": bool(node.get("frozen")),
        "ci": ci,
        "formal_iv": formal_iv,
        "claim_integrity": node.get("claim_integrity"),
        "mergeable": mergeable,
        "merge_guardian": merge_guardian,
        "merge_receipt": merge_receipt,
        "blockers": blockers,
        "dispatch": dispatch_plan,
        "evidence": evidence_section,
        "next_actions": next_actions,
        "gates": gates,
        "uncertainty": sorted(uncertainty),
        "provenance": {
            "generator": "atlas-dag handoff (FEATURE_08)",
            "projection_only": True,
            "grants_no_authority": True,
            "truth_sources": [
                "ATLAS_DAG_SNAPSHOT_V1 (Features 1-5)",
                "FEATURE_03 stack topology",
                "FEATURE_06 dispatch plan",
                "FEATURE_07 evidence graph",
            ],
        },
        "presentation": _presentation(
            mode, node, stack_record, evidence_section, gate_reasons,
            _pool_prohibitions(pool_path)),
    }

    # TOCTOU guard: re-resolve the candidate HEAD from live truth before any
    # packet is emitted. A move => stale, fail closed, no packet.
    live = _live_pr(client, pr_number)
    live_head = live.get("headRefOid") if live else None
    if live_head != head:
        raise HandoffStale(
            f"HANDOFF_STALE_DURING_BUILD:pr={pr_number}:"
            f"built={head}:live={live_head or 'UNKNOWN'}")
    return packet
