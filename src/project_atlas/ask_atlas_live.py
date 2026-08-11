"""AS-2.1 Ask Atlas live path + AS-2.2 Ask Atlas 2 retrieval/compiler wire.

UI != canonical. Graph != authority. Never writes Layer B.
Ask Atlas 2 consumes AS-2.2-RUNTIME-001 hybrid_retrieve + compile_context
outputs only — never invents Knowledge/Graph evidence.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.runtime_22 import (
    SUPPORTED_KINDS,
    Runtime22Error,
    compile_context,
    hybrid_retrieve,
)

PACKAGE_ID = "AS-2.1-ASK-ATLAS-LIVE-001"
ASK2_PACKAGE_ID = "AS-2.2-ASK2-001"
TRUTH_BOUNDARY = "ASK ATLAS LIVE != CANONICAL WRITE / UI!=TRUTH / != AUTHORITY"
ASK2_TRUTH_BOUNDARY = (
    "ASK ATLAS 2 ≠ CANONICAL WRITE / ≠ AUTHORITY / UI ≠ TRUTH / ≠ INVENTED EVIDENCE"
)
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_RETRIEVAL_CAP = 20
_CONTEXT_BUDGET = 20


class AskAtlasLiveError(ValueError):
    """Fail-closed Ask Atlas live error."""


def _pack_id_for_query(query: str) -> str:
    """Deterministic pack id safe for runtime_22.compile_context."""
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
    pack_id = f"ask-{digest}"
    if not _PACK_ID_RE.fullmatch(pack_id):
        raise AskAtlasLiveError("ask-pack-id-invalid")
    return pack_id


def _fuse_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic dedupe by (record_type, record_id); first-wins after sort."""
    fused: dict[tuple[str, str], dict[str, Any]] = {}
    for item in sorted(
        rows,
        key=lambda r: (str(r.get("record_type") or ""), str(r.get("record_id") or "")),
    ):
        key = (str(item.get("record_type") or ""), str(item.get("record_id") or ""))
        if not key[0] or not key[1]:
            continue
        if key not in fused:
            fused[key] = item
    return [fused[k] for k in sorted(fused.keys())]


def _wire_retrieval_and_compiler(vault: Path, query: str) -> dict[str, Any]:
    """Run multi-kind hybrid retrieval then context compile (read-only).

    Missing lexical indexes are recorded as absent — never fabricated.
    Empty hits → UNKNOWN; compile_context still runs on the (possibly empty)
    candidate set so the Ask path always returns honest compiler output.
    """
    kinds_probed: list[str] = []
    kinds_absent: list[str] = []
    kinds_failed: list[str] = []
    raw_candidates: list[dict[str, Any]] = []

    for kind in sorted(SUPPORTED_KINDS):
        try:
            report = hybrid_retrieve(
                vault,
                kind=kind,
                value=query,
                mode="prefix",
                cap=_RETRIEVAL_CAP,
                include_graph_slot=False,
                enable_semantic=False,
            )
        except Runtime22Error:
            kinds_failed.append(kind)
            continue
        except ValueError as exc:
            msg = str(exc)
            if "generated lexical index is missing" in msg or "missing" in msg:
                kinds_absent.append(kind)
            else:
                kinds_failed.append(kind)
            continue
        kinds_probed.append(kind)
        for row in report.get("candidates") or []:
            if isinstance(row, dict):
                raw_candidates.append(row)

    candidates = _fuse_candidates(raw_candidates)
    # Per-kind cap already applied; fused list may still exceed budget — compiler truncates.
    unknown: list[str] = []
    if not kinds_probed and kinds_absent:
        unknown.append("lexical-indexes-absent")
    if kinds_probed and not candidates:
        unknown.append("no-lexical-retrieval-hits")
    if not kinds_probed and not kinds_absent and kinds_failed:
        unknown.append("retrieval-unavailable")

    pack_id = _pack_id_for_query(query)
    try:
        context = compile_context(
            vault,
            pack_id=pack_id,
            candidates=candidates,
            budget=_CONTEXT_BUDGET,
            profile_id="p0-readonly",
            write=False,
        )
        context_status = "active"
    except Runtime22Error as exc:
        # Fail closed on compiler refuse — surface error, never invent entries.
        context = {
            "schema_version": 1,
            "package_id": ASK2_PACKAGE_ID,
            "artifact_kind": "runtime-context-compiler",
            "pack_id": pack_id,
            "status": "refused",
            "error": str(exc),
            "entries": [],
            "entry_count": 0,
            "authority": {
                "level": "derived",
                "llm_authority": False,
                "pilot": False,
                "estate_facts_invented": False,
            },
            "truth_boundary": ASK2_TRUTH_BOUNDARY,
            "generated": {"by": "project-atlas"},
        }
        context_status = "refused"
        unknown.append("context-compiler-refused")

    if (
        context_status == "active"
        and int(context.get("entry_count") or 0) == 0
        and "no-lexical-retrieval-hits" not in unknown
        and "lexical-indexes-absent" not in unknown
    ):
        unknown.append("context-empty")

    status = "matched" if int(context.get("entry_count") or 0) > 0 else "unknown"
    # Explicit inability — never invent an ANSWER body from missing evidence.
    # Matched: callers render from context entries (ANSWER stays None).
    answer: str | None = (
        None
        if status == "matched"
        else "UNKNOWN — no retrieval/compiler evidence for query"
    )

    return {
        "package_id": ASK2_PACKAGE_ID,
        "enabled": True,
        "status": status,
        "ANSWER": answer,
        "EVIDENCE": [
            f"{e['record_type']}:{e['record_id']}"
            for e in (context.get("entries") or [])
            if isinstance(e, dict) and e.get("record_type") and e.get("record_id")
        ],
        "UNKNOWN": sorted(set(unknown)),
        "AUTHORITY": {
            "level": "derived",
            "note": "Ask Atlas 2 consumes runtime_22 retrieval+compiler only",
        },
        "retrieval": {
            "status": (
                "active"
                if candidates
                else ("absent" if kinds_absent and not kinds_probed else "empty")
            ),
            "mode": "prefix",
            "cap": _RETRIEVAL_CAP,
            "kinds_probed": kinds_probed,
            "kinds_absent": kinds_absent,
            "kinds_failed": kinds_failed,
            "candidate_count": len(candidates),
            "candidates": candidates[:_RETRIEVAL_CAP],
            "graph_authority": False,
            "semantic_enabled": False,
            "estate_facts_invented": False,
        },
        "context": context,
        "context_status": context_status,
        "canonical_write": False,
        "ui_truth": False,
        "graph_authority": False,
        "llm_authority": False,
        "truth_boundary": ASK2_TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }


def ask_atlas_live(
    vault: Path,
    *,
    query: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Answer a read-only Ask Atlas query from live vault projections + Ask2 wire."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("web.read")
    q = query.strip()
    if not q or len(q) > 256:
        raise AskAtlasLiveError("ask-query-invalid")
    svc = open_app_service(vault)
    projects = svc.projects()
    knowledge = svc.knowledge()
    health = svc.health()
    q_lower = q.lower()
    matched_projects = [
        p
        for p in projects
        if q_lower in str(p.get("project_id", "")).lower()
        or q_lower in str(p.get("path", "")).lower()
        or q_lower in str(p.get("title", "")).lower()
        or q_lower in str(p.get("name", "")).lower()
    ]
    matched_knowledge = [
        k
        for k in knowledge
        if q_lower in str(k.get("subject") or "").lower()
        or q_lower in str(k.get("answer_id") or "").lower()
        or q_lower in str(k.get("title") or "").lower()
        or q_lower in str(k.get("summary") or "").lower()
    ]
    vault_health = health.get("vault_health") or {}
    health_hits: list[str] = []
    for token in ("health", "rollup", "status", "ops"):
        if token in q_lower:
            health_hits.append(token)
    if str(vault_health.get("rollup", "")).lower() in q_lower:
        health_hits.append("rollup-value")

    ask2 = _wire_retrieval_and_compiler(vault.expanduser().resolve(), q)

    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "query": q,
        "live_ask": True,
        "ask_atlas_2": True,
        "canonical_write": False,
        "ui_truth": False,
        "graph_authority": False,
        "llm_authority": False,
        "matches": {
            "projects": matched_projects[:50],
            "knowledge": matched_knowledge[:50],
            "health_keywords": sorted(set(health_hits)),
        },
        "health": vault_health,
        "ask2": ask2,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
