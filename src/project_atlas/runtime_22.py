"""AS-2.2-RUNTIME-001 — Hybrid Retrieval + Context Compiler P0 (read-only).

Production runtime (not PREP): deterministic multi-slot retrieval fusion and a
budgeted context package with provenance pointers. Never invents estate facts,
never enables semantic/LLM authority, never mutates Layer B.

Truth boundaries:
  HYBRID RETRIEVAL ≠ AUTHORITY / ≠ EMBEDDINGS
  CONTEXT COMPILER ≠ ESTATE FACTS / ≠ PILOT / ≠ LLM AUTHORITY
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

RetrievalMode = Literal["exact", "prefix"]
SUPPORTED_KINDS = frozenset(
    {"source", "claim", "concept", "conflict", "authority", "provenance"}
)


class Runtime22Error(ValueError):
    """Fail-closed AS-2.2-RUNTIME-001 error."""


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

    if cap < 1 or cap > MAX_CAP:
        raise Runtime22Error(f"hybrid-cap-invalid:{cap}")

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
                    provenance_ptrs.append({"kind": "source", "ref": str(ref)})
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
    truncated = len(ordered) > cap
    ordered = ordered[:cap]

    graph_slot: dict[str, Any] = {
        "enabled": include_graph_slot,
        "status": "idle",
        "graph_authority": False,
    }
    if include_graph_slot:
        summary = impact_graph_summary(vault_path)
        graph_slot = {
            "enabled": True,
            "status": "active" if summary.get("available") else "absent",
            "graph_authority": False,
            "summary": summary,
            "note": "GRAPH ≠ AUTHORITY — summary only; never promotes winners",
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
            "cap": cap,
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

    Pipeline (fixed): candidates → authority stamp → budget → package.
    Invent flags / unknown profiles / semantic elevation fail closed.
    """
    require_compatibility_anchor()
    pack_token = pack_id.strip()
    if not _ID_RE.fullmatch(pack_token):
        raise Runtime22Error(f"context-pack-id-invalid:{pack_id!r}")

    profile = profile_id.strip()
    if profile != "p0-readonly":
        raise Runtime22Error(f"context-compiler-profile-unknown:{profile}")

    if budget < 1 or budget > MAX_CAP:
        raise Runtime22Error(f"context-budget-invalid:{budget}")

    if not isinstance(candidates, list):
        raise Runtime22Error("context-candidates-invalid")

    selected: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        record_type = str(raw.get("record_type") or "").strip()
        record_id = str(raw.get("record_id") or "").strip()
        if not record_type or not record_id:
            continue
        if raw.get("authority_level") not in (None, "derived", "none"):
            raise Runtime22Error("context-compiler-authority-spoof")
        selected.append(
            {
                "entry_id": f"{record_type}:{record_id}",
                "record_type": record_type,
                "record_id": record_id,
                "slot": str(raw.get("slot") or "unknown"),
                "authority_level": "derived",
                "provenance": raw.get("provenance")
                if isinstance(raw.get("provenance"), list)
                else [],
            }
        )

    selected.sort(key=lambda e: e["entry_id"])
    truncated = len(selected) > budget
    selected = selected[:budget]

    package: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "artifact_kind": COMPILER_KIND,
        "compat_snapshot_id": SNAPSHOT_ID,
        "pack_id": pack_token,
        "profile_id": profile,
        "budget": budget,
        "entries": selected,
        "entry_count": len(selected),
        "truncated": truncated,
        "pipeline": [
            "candidates",
            "authority_stamp",
            "budget",
            "package",
        ],
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "pilot": False,
            "estate_facts_invented": False,
        },
        "truth_boundary": TRUTH_COMPILER,
        "generated": {"by": "project-atlas"},
    }

    if write:
        out = (
            vault.expanduser().resolve()
            / "generated"
            / "context-compiler"
            / f"{pack_token}-context-compiler.json"
        )
        _atomic_write_json(out, package)
        package = {**package, "output_path": str(out.as_posix())}

    return package


def package_to_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON serialization (NFR-001 — no wall-clock)."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
