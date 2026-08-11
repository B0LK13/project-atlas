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
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.retrieval import VaultRetriever
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
SUPPORTED_KINDS = frozenset(
    {"source", "claim", "concept", "conflict", "authority", "provenance"}
)


class Runtime22Error(ValueError):
    """Fail-closed AS-2.2-RUNTIME-001 error."""


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


def _record_present_in_vault(
    retriever: VaultRetriever, record_type: str, record_id: str
) -> bool:
    """True when ``record_id`` resolves via AS-RET-001 lexical indexes."""
    if record_type not in SUPPORTED_KINDS:
        return False
    try:
        hits = retriever.lookup(record_type, record_id, prefix=False)
    except ValueError:
        return False
    return any(hit.record_id == record_id for hit in hits)


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
    mode: RetrievalMode = "exact",
    cap: int = DEFAULT_CAP,
    include_graph_slot: bool = False,
    enable_semantic: bool = False,
) -> dict[str, Any]:
    """Run P0 hybrid retrieval: lexical (+ optional derived graph summary).

    Semantic slot remains disabled; requesting it fails closed.
    Graph narrative fields are fixed constants (GRAPH ≠ AUTHORITY).
    """
    require_compatibility_anchor()
    if enable_semantic:
        raise Runtime22Error(
            "semantic-slot-forbidden:AS-2.2-RUNTIME-001-no-llm-authority"
        )

    kind_token = kind.strip()
    if kind_token not in SUPPORTED_KINDS:
        raise Runtime22Error(f"hybrid-kind-unsupported:{kind_token}")

    query_value = value.strip()
    if not query_value:
        raise Runtime22Error("hybrid-value-empty")

    if mode not in ("exact", "prefix"):
        raise Runtime22Error(f"hybrid-mode-invalid:{mode}")

    cap_n = _require_int_in_range("hybrid-cap", cap, 1, MAX_CAP)

    vault_path = vault.expanduser().resolve()
    retriever = VaultRetriever(vault_path)
    use_prefix = mode == "prefix"
    lexical_hits = retriever.lookup(kind_token, query_value, prefix=use_prefix)
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
    candidates: list[dict[str, Any]],
    budget: int = DEFAULT_CAP,
    profile_id: str = "p0-readonly",
    write: bool = False,
) -> dict[str, Any]:
    """Compile a budgeted context package from hybrid candidates (P0).

    Pipeline (fixed): candidates → vault presence → provenance gate →
    authority stamp → budget → package.
    Invented vault-absent IDs and empty provenance fail closed
    (RT-ADV-001 / RT-ADV-004). Unknown profiles / semantic elevation fail closed.
    """
    require_compatibility_anchor()
    pack_token = pack_id.strip()
    if not _ID_RE.fullmatch(pack_token):
        raise Runtime22Error(f"context-pack-id-invalid:{pack_id!r}")

    profile = profile_id.strip()
    if profile != "p0-readonly":
        raise Runtime22Error(f"context-compiler-profile-unknown:{profile}")

    budget_n = _require_int_in_range("context-budget", budget, 1, MAX_CAP)

    if not isinstance(candidates, list):
        raise Runtime22Error("context-candidates-invalid")

    vault_path = vault.expanduser().resolve()
    retriever = VaultRetriever(vault_path)

    selected: list[dict[str, Any]] = []
    skipped_malformed = 0
    provenance_elems_dropped = 0
    for raw in candidates:
        if not isinstance(raw, dict):
            skipped_malformed += 1
            continue
        record_type = str(raw.get("record_type") or "").strip()
        record_id = str(raw.get("record_id") or "").strip()
        if not record_type or not record_id:
            skipped_malformed += 1
            continue
        if raw.get("authority_level") not in (None, "derived", "none"):
            raise Runtime22Error("context-compiler-authority-spoof")
        # RT-ADV-001: refuse invented vault-absent records (never stamp honesty lie).
        if not _record_present_in_vault(retriever, record_type, record_id):
            raise Runtime22Error(
                f"context-compiler-record-absent:{record_type}:{record_id}"
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
        selected.append(
            {
                "entry_id": f"{record_type}:{record_id}",
                "record_type": record_type,
                "record_id": record_id,
                "slot": str(raw.get("slot") or "unknown"),
                "authority_level": "derived",
                "provenance": prov,
            }
        )

    # Deterministic dedupe by entry_id before budget (sorted first-wins).
    selected.sort(key=lambda e: e["entry_id"])
    fused_entries: dict[str, dict[str, Any]] = {}
    for entry in selected:
        eid = str(entry["entry_id"])
        if eid not in fused_entries:
            fused_entries[eid] = entry
    duplicates_collapsed = len(selected) - len(fused_entries)
    ordered = [fused_entries[k] for k in sorted(fused_entries.keys())]
    truncated = len(ordered) > budget_n
    ordered = ordered[:budget_n]

    package: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "artifact_kind": COMPILER_KIND,
        "compat_snapshot_id": SNAPSHOT_ID,
        "pack_id": pack_token,
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
        "pipeline": [
            "candidates",
            "vault_presence",
            "provenance_gate",
            "authority_stamp",
            "budget",
            "package",
        ],
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
