"""AS-2.2-RUNTIME-001 — Hybrid Retrieval + Context Compiler (read-only deepen).

Production runtime (not PREP): deterministic multi-slot retrieval fusion and a
budgeted context package with provenance pointers. Never invents estate facts,
never enables semantic/LLM authority, never mutates Layer B.

Truth boundaries:
  HYBRID RETRIEVAL ≠ AUTHORITY / ≠ EMBEDDINGS
  CONTEXT COMPILER ≠ ESTATE FACTS / ≠ PILOT / ≠ LLM AUTHORITY

Input hygiene (P1 deepen / RUNTIME-ADV remedi):
  - Malformed candidate rows (non-dict / missing ids) are skipped, counted.
  - Vault-absent invented records fail closed (RT-ADV-001) — never package
    invented IDs under ``estate_facts_invented=false``.
  - Empty / missing provenance after sanitize fails closed (RT-ADV-004).
  - Provenance elems must be ``{kind, ref}`` with safe relative refs; others drop.
  - Duplicate ``entry_id`` values collapse before budget (first-wins by sort).

P2 deepen (ADVANCE-005 C1):
  - Profile ``p2-readonly`` runs authority → freshness → conflicts → relevance
    → budget with objective signals and pipeline receipt.
  - Freshness laundering (caller fresh vs portfolio stale) fails closed.
  - Unresolved conflicts retained as sidecars (no silent winner) or excluded.
  - Hard budget overflow fails closed when ``on_overflow=fail``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.hybrid_retrieval import MAX_QUERY_CHARS, MAX_QUERY_TERMS
from project_atlas.retrieval import VaultRetriever, _in_project_scope
from project_atlas.retrieval_fusion import tokenize
from project_atlas.web_api.graph import impact_graph_summary

PACKAGE_ID = "AS-2.2-RUNTIME-001"
HYBRID_KIND = "runtime-hybrid-retrieval"
COMPILER_KIND = "runtime-context-compiler"
TRUTH_HYBRID = "HYBRID RETRIEVAL ≠ AUTHORITY / ≠ EMBEDDINGS"
TRUTH_COMPILER = "CONTEXT COMPILER ≠ ESTATE FACTS / ≠ PILOT / ≠ LLM AUTHORITY"
DEFAULT_CAP = 20
MAX_CAP = 100
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_PROV_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_PROV_KINDS = frozenset(
    {"source", "receipt", "index", "claim", "concept", "other"}
)
_GRAPH_NOTE = "GRAPH ≠ AUTHORITY — summary only; never promotes winners"

RetrievalMode = Literal["exact", "prefix"]
OverflowPolicy = Literal["truncate", "fail"]
SUPPORTED_KINDS = frozenset(
    {"source", "claim", "concept", "conflict", "authority", "provenance"}
)
PROFILE_P0 = "p0-readonly"
PROFILE_P2 = "p2-readonly"
SUPPORTED_PROFILES = frozenset({PROFILE_P0, PROFILE_P2})
# Objective Core-compatible authority labels (no subjective trust scores).
_AUTHORITY_RANK: dict[str, int] = {
    "primary": 0,
    "validated-execution": 1,
    "maintained": 2,
    "derived": 3,
    "generated": 4,
    "inferred": 5,
    "pending": 6,
    "conflicting": 7,
    "rejected": 8,
}
_CALLER_AUTHORITY_ALLOWED = frozenset({"derived", "none", "generated", "inferred"})
_FRESHNESS_ALLOWED = frozenset({"fresh", "stale", "unknown"})
_FRESHNESS_RANK = {"fresh": 0, "unknown": 1, "stale": 2}
_P0_PIPELINE = [
    "candidates",
    "vault_presence",
    "provenance_gate",
    "authority_stamp",
    "budget",
    "package",
]
_P2_PIPELINE = [
    "candidates",
    "vault_presence",
    "provenance_gate",
    "authority",
    "freshness",
    "conflicts",
    "relevance",
    "budget",
    "package",
]


class Runtime22Error(ValueError):
    """Fail-closed AS-2.2-RUNTIME-001 error."""


def _require_project_scope(project_id: str, *, token: str) -> str:
    """Require a non-empty project scope (fail-closed; default-deny cross-project).

    Mirrors :func:`project_atlas.hybrid_retrieval._require_project_scope` so the
    runtime surface enforces the same project-scope contract as the AS-2.0
    hybrid surface (CLAUDE-009 cross-project leak remediation).
    """
    scope = project_id.strip()
    if not scope:
        raise Runtime22Error(token)
    return scope


def _require_query_bounds(value: str, *, label: str) -> None:
    """Reject over-length / too-many-term queries (reuses AS-2.0 bounds).

    Bounds mirror :data:`hybrid_retrieval.MAX_QUERY_CHARS` /
    :data:`hybrid_retrieval.MAX_QUERY_TERMS` so the runtime query path is
    consistent with the AS-2.0 hybrid surface (CLAUDE-013 residual).
    """
    if len(value) > MAX_QUERY_CHARS:
        raise Runtime22Error(f"{label}-query-too-long:{len(value)}")
    distinct_terms = len(set(tokenize(value)))
    if distinct_terms > MAX_QUERY_TERMS:
        raise Runtime22Error(f"{label}-query-too-many-terms:{distinct_terms}")


def _require_int_in_range(label: str, value: object, lo: int, hi: int) -> int:
    """Reject bool/float/str; require inclusive int range (fail-closed)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise Runtime22Error(f"{label}-invalid:{value!r}")
    if value < lo or value > hi:
        raise Runtime22Error(f"{label}-invalid:{value}")
    return value


def _sanitize_provenance(raw: object) -> tuple[list[dict[str, str]], int]:
    """Keep only safe ``{kind, ref}`` pointers; count dropped elems.

    Non-list input → ``([], 0)``; callers must fail closed when empty
    after sanitize (RT-ADV-004). Never invent replacement pointers.
    """
    if not isinstance(raw, list):
        return [], 0
    cleaned: list[dict[str, str]] = []
    dropped = 0
    for item in raw:
        if not isinstance(item, dict):
            dropped += 1
            continue
        kind = str(item.get("kind") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if kind not in _PROV_KINDS:
            dropped += 1
            continue
        if (
            not ref
            or ".." in ref
            or ref.startswith(("/", "\\"))
            or not _PROV_REF_RE.fullmatch(ref)
        ):
            dropped += 1
            continue
        cleaned.append({"kind": kind, "ref": ref})
    return cleaned, dropped


def _record_presence(
    retriever: VaultRetriever,
    record_type: str,
    record_id: str,
    *,
    project_id: str,
) -> tuple[bool, bool]:
    """Return ``(present_anywhere, in_project_scope)`` for a record.

    Presence resolves via AS-RET-001 lexical indexes. Scope membership reuses
    :func:`retrieval._in_project_scope` (fail-closed on records lacking a
    project id), so a record that exists only in a sibling project is present
    but out of scope — the caller must fail closed (CLAUDE-009).
    """
    if record_type not in SUPPORTED_KINDS:
        return False, False
    try:
        hits = retriever.lookup(record_type, record_id, prefix=False)
    except ValueError:
        return False, False
    present = False
    in_scope = False
    for hit in hits:
        if hit.record_id != record_id:
            continue
        present = True
        if _in_project_scope(hit.record_type, hit.record, project_id):
            in_scope = True
    return present, in_scope


def _load_portfolio_freshness(vault: Path) -> dict[str, str]:
    """Map source_id → freshness label from portfolio report (objective only)."""
    path = vault / "generated" / "portfolio" / "stale-knowledge.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    labels: dict[str, str] = {}
    sources = raw.get("sources") if isinstance(raw, dict) else None
    if not isinstance(sources, list):
        return {}
    for item in sources:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        freshness = item.get("freshness")
        if isinstance(source_id, str) and freshness in _FRESHNESS_ALLOWED:
            labels[source_id] = freshness
    return labels


def _load_unresolved_claim_conflicts(
    vault: Path,
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    """Map claim_id → conflict_ids and conflict_id → unresolved record metadata."""
    root = vault / "review" / "conflicts"
    claim_map: dict[str, set[str]] = {}
    conflict_records: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return {}, {}
    for path in sorted(root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        entries = raw.get("entries") if isinstance(raw, dict) else None
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            state = str(entry.get("state") or "").strip().lower()
            if state != "unresolved":
                continue
            conflict_id = str(entry.get("conflict_id") or "").strip()
            if not conflict_id:
                continue
            claim_ids = entry.get("claim_ids")
            if not isinstance(claim_ids, list):
                continue
            sorted_claim_ids = sorted(
                cid.strip() for cid in claim_ids if isinstance(cid, str) and cid.strip()
            )
            if not sorted_claim_ids:
                continue
            conflict_records[conflict_id] = {
                "conflict_id": conflict_id,
                "claim_ids": sorted_claim_ids,
                "subject": str(entry.get("subject") or "").strip(),
                "field": str(entry.get("field") or "").strip(),
            }
            for cid in sorted_claim_ids:
                claim_map.setdefault(cid, set()).add(conflict_id)
    return (
        {cid: sorted(ids) for cid, ids in sorted(claim_map.items())},
        dict(sorted(conflict_records.items())),
    )


def _portfolio_keys_for_ref(ref: str) -> set[str]:
    """Match bare source_id or trailing path segment used as source_id."""
    candidates = {ref}
    if "/" in ref:
        candidates.add(ref.rsplit("/", 1)[-1])
        if ref.endswith(".md"):
            candidates.add(ref.rsplit("/", 1)[-1][: -len(".md")])
    return candidates


def _aggregate_portfolio_freshness(
    entry: dict[str, Any], *, portfolio: dict[str, str]
) -> str | None:
    """Conservative order-independent freshness across all portfolio hits."""
    observed: list[str] = []
    matched_keys: set[str] = set()
    for ptr in entry.get("provenance") or []:
        if not isinstance(ptr, dict):
            continue
        ref = str(ptr.get("ref") or "")
        for key in _portfolio_keys_for_ref(ref):
            if key in portfolio and key not in matched_keys:
                matched_keys.add(key)
                observed.append(portfolio[key])
    if not observed:
        return None
    return max(observed, key=lambda label: _FRESHNESS_RANK[label])


def _freshness_for_entry(
    entry: dict[str, Any],
    *,
    portfolio: dict[str, str],
    caller_freshness: object,
) -> str:
    """Resolve freshness; unknown ≠ fresh; refuse laundering stale→fresh."""
    if caller_freshness is not None:
        label = str(caller_freshness).strip()
        if label not in _FRESHNESS_ALLOWED:
            raise Runtime22Error(f"context-compiler-freshness-invalid:{label}")
    else:
        label = None

    observed = _aggregate_portfolio_freshness(entry, portfolio=portfolio)

    if observed is None and label is None:
        return "unknown"
    if observed is None:
        # Caller-supplied without portfolio corroboration → never invent fresh.
        return "unknown" if label == "fresh" else str(label)
    if label == "fresh" and observed == "stale":
        raise Runtime22Error(
            f"context-compiler-freshness-launder:{entry['entry_id']}"
        )
    return observed


def _authority_for_entry(
    *,
    caller_level: object,
    conflict_state: str,
) -> str:
    """Stamp objective authority; never elevate to primary/canonical/llm."""
    if caller_level not in (None, *_CALLER_AUTHORITY_ALLOWED):
        raise Runtime22Error("context-compiler-authority-spoof")
    if conflict_state == "unresolved":
        return "conflicting"
    if caller_level in ("generated", "inferred"):
        return str(caller_level)
    return "derived"


def _reason_included(
    *,
    authority: str,
    freshness: str,
    conflict_state: str,
) -> str:
    if conflict_state == "unresolved":
        return "conflict-sidecar"
    if authority == "primary":
        return "authority-primary"
    if authority == "validated-execution":
        return "authority-validated"
    if authority == "maintained":
        return "authority-maintained"
    if freshness == "fresh":
        return "freshness-current"
    return "explicit-candidate"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def hybrid_retrieve(
    vault: Path,
    *,
    kind: str,
    value: str,
    project_id: str,
    mode: RetrievalMode = "exact",
    cap: int = DEFAULT_CAP,
    include_graph_slot: bool = False,
    enable_semantic: bool = False,
) -> dict[str, Any]:
    """Run P0 hybrid retrieval: lexical (+ optional derived graph summary).

    Semantic slot remains disabled; requesting it fails closed.
    Graph narrative fields are fixed constants (GRAPH ≠ AUTHORITY).
    ``project_id`` is required — cross-project retrieval is denied by default
    (fail-closed), mirroring the AS-2.0 hybrid surface (CLAUDE-009).
    """
    require_compatibility_anchor()
    if enable_semantic:
        raise Runtime22Error(
            "semantic-slot-forbidden:AS-2.2-RUNTIME-001-no-llm-authority"
        )

    scope = _require_project_scope(
        project_id, token="runtime-hybrid-project-scope-required"
    )

    kind_token = kind.strip()
    if kind_token not in SUPPORTED_KINDS:
        raise Runtime22Error(f"hybrid-kind-unsupported:{kind_token}")

    query_value = value.strip()
    if not query_value:
        raise Runtime22Error("hybrid-value-empty")
    _require_query_bounds(query_value, label="hybrid")

    if mode not in ("exact", "prefix"):
        raise Runtime22Error(f"hybrid-mode-invalid:{mode}")

    cap_n = _require_int_in_range("hybrid-cap", cap, 1, MAX_CAP)

    vault_path = vault.expanduser().resolve()
    retriever = VaultRetriever(vault_path)
    use_prefix = mode == "prefix"
    lexical_hits = retriever.lookup(
        kind_token, query_value, prefix=use_prefix, project_id=scope
    )
    slot_name = "lexical_prefix" if use_prefix else "lexical_exact"

    candidates: list[dict[str, Any]] = []
    for hit in lexical_hits:
        provenance_ptrs: list[dict[str, str]] = [
            {
                "kind": "index",
                "ref": f"generated/indexes/{hit.record_type}",
            }
        ]
        for item in hit.provenance[:3]:
            ref = item.get("ref") or item.get("source_id") or item.get("path")
            if ref:
                safe, _dropped = _sanitize_provenance(
                    [{"kind": "source", "ref": str(ref)}]
                )
                provenance_ptrs.extend(safe)
        candidates.append(
            {
                "record_type": hit.record_type,
                "record_id": hit.record_id,
                "slot": slot_name,
                "authority_level": "derived",
                "provenance": provenance_ptrs,
            }
        )

    # Deterministic fuse: sort + dedupe by (record_type, record_id), then cap.
    fused: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        key = (str(item["record_type"]), str(item["record_id"]))
        if key not in fused:
            fused[key] = item
    ordered = [fused[k] for k in sorted(fused.keys())]
    truncated = len(ordered) > cap_n
    ordered = ordered[:cap_n]

    graph_slot: dict[str, Any] = {
        "enabled": include_graph_slot,
        "status": "idle",
        "graph_authority": False,
    }
    if include_graph_slot:
        summary = impact_graph_summary(vault_path)
        # Counts only — never echo attacker-controlled note/truth_boundary.
        safe_summary = {
            "available": bool(summary.get("available")),
            "node_count": int(summary.get("node_count") or 0),
            "edge_count": int(summary.get("edge_count") or 0),
            "graph_authority": False,
        }
        graph_slot = {
            "enabled": True,
            "status": "active" if safe_summary["available"] else "absent",
            "graph_authority": False,
            "summary": safe_summary,
            "note": _GRAPH_NOTE,
        }

    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "artifact_kind": HYBRID_KIND,
        "compat_snapshot_id": SNAPSHOT_ID,
        "query": {
            "kind": kind_token,
            "value": query_value,
            "mode": mode,
            "cap": cap_n,
            "project_id": scope,
        },
        "slots": {
            "lexical_exact": {
                "enabled": not use_prefix,
                "status": "active" if not use_prefix else "idle",
            },
            "lexical_prefix": {
                "enabled": use_prefix,
                "status": "active" if use_prefix else "idle",
            },
            "graph": graph_slot,
            "semantic": {
                "enabled": False,
                "status": "disabled",
                "reason": "semantic-disabled-no-llm-authority",
            },
        },
        "candidates": ordered,
        "candidate_count": len(ordered),
        "truncated": truncated,
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "note": "P0 fusion over AS-RET-001 lexical indexes only",
        },
        "truth_boundary": TRUTH_HYBRID,
        "generated": {"by": "project-atlas"},
    }


def compile_context(
    vault: Path,
    *,
    pack_id: str,
    candidates: list[Any],
    project_id: str,
    budget: int = DEFAULT_CAP,
    profile_id: str = PROFILE_P0,
    write: bool = False,
    on_overflow: OverflowPolicy = "truncate",
    include_unresolved_conflicts: bool = True,
) -> dict[str, Any]:
    """Compile a budgeted context package from hybrid candidates.

    P0 pipeline: candidates → vault presence → provenance gate →
    authority stamp → budget → package.

    P2 pipeline (``p2-readonly``): adds authority → freshness → conflicts →
    relevance before budget. Invented vault-absent IDs and empty provenance
    fail closed (RT-ADV-001 / RT-ADV-004). Unknown profiles / authority spoof /
    freshness laundering / hard budget overflow fail closed.

    ``project_id`` is required — every candidate must resolve inside that
    project scope; records from a sibling project fail closed (default-deny
    cross-project, CLAUDE-009).
    """
    require_compatibility_anchor()
    scope = _require_project_scope(
        project_id, token="runtime-context-project-scope-required"
    )
    pack_token = pack_id.strip()
    if not _ID_RE.fullmatch(pack_token):
        raise Runtime22Error(f"context-pack-id-invalid:{pack_id!r}")

    profile = profile_id.strip()
    if profile not in SUPPORTED_PROFILES:
        raise Runtime22Error(f"context-compiler-profile-unknown:{profile}")

    if on_overflow not in ("truncate", "fail"):
        raise Runtime22Error(f"context-compiler-overflow-invalid:{on_overflow}")

    budget_n = _require_int_in_range("context-budget", budget, 1, MAX_CAP)

    if not isinstance(candidates, list):
        raise Runtime22Error("context-candidates-invalid")

    vault_path = vault.expanduser().resolve()
    retriever = VaultRetriever(vault_path)
    p2 = profile == PROFILE_P2
    portfolio = _load_portfolio_freshness(vault_path) if p2 else {}
    claim_conflicts: dict[str, list[str]] = {}
    conflict_records: dict[str, dict[str, Any]] = {}
    if p2:
        claim_conflicts, conflict_records = _load_unresolved_claim_conflicts(
            vault_path
        )

    selected: list[dict[str, Any]] = []
    skipped_malformed = 0
    provenance_elems_dropped = 0
    excluded_conflicts = 0
    excluded_conflicts_detail: list[dict[str, Any]] = []
    excluded_conflict_ids_seen: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, dict):
            skipped_malformed += 1
            continue
        record_type = str(raw.get("record_type") or "").strip()
        record_id = str(raw.get("record_id") or "").strip()
        if not record_type or not record_id:
            skipped_malformed += 1
            continue
        # RT-ADV-001: refuse invented vault-absent records (never stamp honesty lie).
        # CLAUDE-009: refuse records that resolve only in a sibling project scope.
        present, in_scope = _record_presence(
            retriever, record_type, record_id, project_id=scope
        )
        if not present:
            raise Runtime22Error(
                f"context-compiler-record-absent:{record_type}:{record_id}"
            )
        if not in_scope:
            raise Runtime22Error(
                f"context-compiler-project-scope-mismatch:{record_type}:{record_id}"
            )
        # RT-ADV-004: refuse missing/empty provenance (no invented backfill).
        if "provenance" not in raw or raw.get("provenance") is None:
            raise Runtime22Error(
                f"context-compiler-provenance-missing:{record_type}:{record_id}"
            )
        if not isinstance(raw.get("provenance"), list):
            raise Runtime22Error(
                f"context-compiler-provenance-invalid:{record_type}:{record_id}"
            )
        prov, dropped = _sanitize_provenance(raw.get("provenance"))
        provenance_elems_dropped += dropped
        if not prov:
            raise Runtime22Error(
                f"context-compiler-provenance-empty:{record_type}:{record_id}"
            )

        entry: dict[str, Any] = {
            "entry_id": f"{record_type}:{record_id}",
            "record_type": record_type,
            "record_id": record_id,
            "slot": str(raw.get("slot") or "unknown"),
            "provenance": prov,
        }

        if p2:
            conflict_ids = (
                claim_conflicts.get(record_id, [])
                if record_type == "claim"
                else []
            )
            if conflict_ids:
                if not include_unresolved_conflicts:
                    excluded_conflicts += 1
                    for conflict_id in conflict_ids:
                        if conflict_id in excluded_conflict_ids_seen:
                            continue
                        excluded_conflict_ids_seen.add(conflict_id)
                        record = conflict_records.get(conflict_id, {})
                        excluded_conflicts_detail.append(
                            {
                                "conflict_id": conflict_id,
                                "claim_ids": record.get("claim_ids", conflict_ids),
                                "subject": record.get("subject", ""),
                                "field": record.get("field", ""),
                                "excluded_claim_id": record_id,
                            }
                        )
                    continue
                conflict_state = "unresolved"
            else:
                conflict_state = "none"
            authority = _authority_for_entry(
                caller_level=raw.get("authority_level"),
                conflict_state=conflict_state,
            )
            freshness = _freshness_for_entry(
                entry,
                portfolio=portfolio,
                caller_freshness=raw.get("freshness"),
            )
            entry["authority_level"] = authority
            entry["freshness"] = freshness
            entry["conflict_state"] = conflict_state
            if conflict_ids:
                entry["conflict_ids"] = conflict_ids
            entry["reason_included"] = _reason_included(
                authority=authority,
                freshness=freshness,
                conflict_state=conflict_state,
            )
        else:
            if raw.get("authority_level") not in (None, "derived", "none"):
                raise Runtime22Error("context-compiler-authority-spoof")
            entry["authority_level"] = "derived"

        selected.append(entry)

    # Deterministic dedupe by entry_id before budget (sorted first-wins).
    selected.sort(key=lambda e: e["entry_id"])
    fused_entries: dict[str, dict[str, Any]] = {}
    for entry in selected:
        eid = str(entry["entry_id"])
        if eid not in fused_entries:
            fused_entries[eid] = entry
    duplicates_collapsed = len(selected) - len(fused_entries)
    ordered = [fused_entries[k] for k in sorted(fused_entries.keys())]

    if p2:
        # Relevance: authority → freshness → conflict → entry_id (stable).
        ordered.sort(
            key=lambda e: (
                _AUTHORITY_RANK.get(str(e["authority_level"]), 99),
                _FRESHNESS_RANK.get(str(e["freshness"]), 99),
                0 if e["conflict_state"] == "none" else 1,
                str(e["entry_id"]),
            )
        )
        for idx, entry in enumerate(ordered):
            entry["relevance_rank"] = idx

    overflow_occurred = len(ordered) > budget_n
    dropped_count = max(0, len(ordered) - budget_n)
    if overflow_occurred and on_overflow == "fail":
        raise Runtime22Error(
            f"context-compiler-budget-overflow:{len(ordered)}>{budget_n}"
        )
    truncated = overflow_occurred and on_overflow == "truncate"
    ordered = ordered[:budget_n]
    if p2 and truncated:
        for entry in ordered:
            if entry.get("reason_included") == "explicit-candidate":
                entry["reason_included"] = "budget-retained"

    unresolved_retained = sum(
        1 for e in ordered if e.get("conflict_state") == "unresolved"
    )

    package: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "artifact_kind": COMPILER_KIND,
        "compat_snapshot_id": SNAPSHOT_ID,
        "pack_id": pack_token,
        "project_id": scope,
        "profile_id": profile,
        "budget": budget_n,
        "entries": ordered,
        "entry_count": len(ordered),
        "truncated": truncated,
        "input_hygiene": {
            "skipped_malformed": skipped_malformed,
            "duplicates_collapsed": duplicates_collapsed,
            "provenance_elems_dropped": provenance_elems_dropped,
            "empty_provenance_policy": "refuse",
        },
        "pipeline": list(_P2_PIPELINE if p2 else _P0_PIPELINE),
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "pilot": False,
            "estate_facts_invented": False,
            "candidates_caller_supplied": True,
        },
        "truth_boundary": TRUTH_COMPILER,
        "generated": {"by": "project-atlas"},
    }

    if p2:
        package["on_overflow"] = on_overflow
        package["include_unresolved_conflicts"] = bool(
            include_unresolved_conflicts
        )
        pipeline_receipt: dict[str, Any] = {
            "candidates_in": len(candidates),
            "items_out": len(ordered),
            "truncated": truncated,
            "overflow": {
                "occurred": overflow_occurred,
                "dropped_count": dropped_count if truncated else 0,
                "policy": on_overflow,
            },
            "unresolved_conflicts_retained": unresolved_retained,
            "conflicts_excluded": excluded_conflicts,
            "freshness_unknown_count": sum(
                1 for e in ordered if e.get("freshness") == "unknown"
            ),
        }
        if excluded_conflicts_detail:
            pipeline_receipt["excluded_conflicts_detail"] = (
                excluded_conflicts_detail
            )
            pipeline_receipt["excluded_conflict_ids"] = sorted(
                excluded_conflict_ids_seen
            )
        package["pipeline_receipt"] = pipeline_receipt

    if write:
        rel = f"generated/context-compiler/{pack_token}-context-compiler.json"
        out = vault_path / Path(rel)
        # On-disk artifact omits output_path (host-portable bytes).
        _atomic_write_json(out, package)
        # Return uses vault-relative POSIX path only (not host-absolute).
        package = {**package, "output_path": rel}

    return package


def package_to_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON serialization (NFR-001 — no wall-clock)."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
