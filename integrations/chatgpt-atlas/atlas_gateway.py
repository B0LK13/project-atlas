"""Atlas read-only gateway for the ChatGPT app (ATLAS-FOR-CHATGPT-READONLY-001).

Isolated integration surface. Reuses the *current* Atlas read-only product
behavior (``project_atlas.web_api`` + generated artifacts) and NEVER duplicates
Atlas truth logic, never writes, and never imports ingestion / compilation
writers. All results are bounded and stamped with the Atlas trust invariants.

Data source is the Phase-A DEMO_FIXTURE vault only:
``source_class = DEMO_FIXTURE`` (never AUTHENTIC_PILOT / PRIVATE_OWNER_ESTATE).

Nothing here is a proven claim or an interpretation: search results are
references, evidence is evidence (not interpretation), and graph is not
authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from project_atlas.web_api import (
    impact_graph_summary,
    list_knowledge_answers,
    list_projects,
    read_status,
)

SOURCE_CLASS = "DEMO_FIXTURE"
MAX_RESULTS = 50
# Hard ceiling on serialized structuredContent (UTF-8). Oversized payloads are
# fail-closed — replaced with a bounded stub, never truncated mid-object with leaks.
MAX_RESPONSE_BYTES = 65_536

# Section 37 — trust invariants echoed on every ChatGPT-facing result.
INVARIANTS: dict[str, Any] = {
    "source_class": SOURCE_CLASS,
    "authentic_pilot": False,
    "ui_canonical": False,
    "graph_authority": False,
    "llm_output_authority": False,
    "unknown_equals_healthy": False,
    "search_result_is_proven_claim": False,
    "evidence_is_interpretation": False,
}


@dataclass(frozen=True)
class ToolResult:
    """MCP-shaped result: structuredContent + narration + widget-only meta."""

    structured_content: dict[str, Any]
    content: str
    meta: dict[str, Any] = field(default_factory=dict)


class GatewayError(ValueError):
    """Raised for malformed tool arguments (never for absent evidence)."""


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return 10
    try:
        value = int(limit)
    except (TypeError, ValueError) as exc:
        raise GatewayError(f"limit must be an integer: {limit!r}") from exc
    return max(1, min(MAX_RESULTS, value))


def _bound_items(items: list[Any], *, limit: int = MAX_RESULTS) -> tuple[list[Any], bool]:
    """Cap list length; return (capped_items, truncated)."""
    if len(items) <= limit:
        return list(items), False
    return list(items[:limit]), True


def _seal(
    structured: dict[str, Any],
    content: str,
    meta: dict[str, Any] | None = None,
) -> ToolResult:
    """Enforce hard response-size budget; fail closed without leaking oversized data."""
    payload = json.dumps(structured, sort_keys=True, default=str)
    if len(payload.encode("utf-8")) <= MAX_RESPONSE_BYTES:
        return ToolResult(structured, content, meta or {})
    sealed = {
        "error": "response_too_large",
        "truncated": True,
        "note": "Result exceeded hard size budget; withheld to prevent over-share.",
        **INVARIANTS,
    }
    return ToolResult(
        sealed,
        "UNKNOWN — response exceeded size budget (fail closed).",
        meta or {},
    )


def _load_index(vault: Path, name: str) -> dict[str, Any]:
    path = vault / "generated" / "indexes" / f"{name}.json"
    return _load_json_object(path)


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _project_ids(vault: Path) -> list[str]:
    return [p["project_id"] for p in list_projects(vault)]


def _dependency_edges(vault: Path) -> dict[str, list[str]]:
    """Return {project_id: [dependency_target, ...]} from the portfolio report.

    This is a derived cross-project projection (Graph != authority).
    """
    report = _load_json_object(vault / "generated" / "portfolio" / "dependency-report.json")
    projects = report.get("projects")
    out: dict[str, list[str]] = {}
    if isinstance(projects, dict):
        for pid, edges in projects.items():
            targets: list[str] = []
            if isinstance(edges, list):
                for edge in edges:
                    target = edge.get("target") if isinstance(edge, dict) else None
                    if isinstance(target, str) and target not in targets:
                        targets.append(target)
            out[str(pid)] = sorted(targets)
    return out


def _evidence_count(vault: Path, project_id: str) -> int:
    """Count source-lineage provenance entries attributed to a project."""
    prov = _load_index(vault, "provenance")
    by_lineage = prov.get("by_source_lineage_id")
    if not isinstance(by_lineage, dict):
        return 0
    return sum(1 for projects in by_lineage.values() if isinstance(projects, list) and project_id in projects)


def _count_for_project(vault: Path, index_name: str, project_id: str) -> int:
    index = _load_index(vault, index_name)
    by_project = index.get("by_project_id")
    if not isinstance(by_project, dict):
        return 0
    ids = by_project.get(project_id)
    return len(ids) if isinstance(ids, list) else 0


def _unknowns(vault: Path, project_id: str, knowledge_count: int, conflict_count: int) -> list[str]:
    """Explicit, honest UNKNOWNs (absent evidence is never 'healthy')."""
    unknowns: list[str] = []
    if impact_graph_summary(vault).get("available") is False:
        unknowns.append("impact_graph_absent")
    status = read_status(vault)
    health = status.get("health") if isinstance(status, dict) else None
    if isinstance(health, dict) and health.get("rollup") == "unknown":
        unknowns.append("ops_health_unknown")
    if knowledge_count == 0:
        unknowns.append("no_compiled_answers")
    if conflict_count == 0:
        unknowns.append("no_detected_conflicts")
    return unknowns


# --------------------------------------------------------------------------- #
# Tools (all READ ONLY)
# --------------------------------------------------------------------------- #


def search(vault: Path, query: str, project_scope: str | None = None, limit: int | None = None) -> ToolResult:
    """Locate Atlas references (projects / knowledge) for a query. READ ONLY."""
    if not isinstance(query, str):
        raise GatewayError("query must be a string")
    needle = query.strip().lower()
    cap = _clamp_limit(limit)
    projects = list_projects(vault)
    if project_scope:
        projects = [p for p in projects if p["project_id"] == project_scope]

    results: list[dict[str, Any]] = []
    for project in projects:
        pid = project["project_id"]
        if not needle or needle in pid.lower():
            results.append(
                {"type": "project", "id": pid, "project_id": pid, "title": pid, "ref": f"project:{pid}"}
            )

    for answer in list_knowledge_answers(vault):
        haystack = " ".join(
            str(part)
            for part in (
                answer.get("answer_id"),
                answer.get("subject"),
                answer.get("field"),
                answer.get("title"),
                answer.get("summary"),
                answer.get("value_text"),
                answer.get("path"),
            )
            if part
        ).lower()
        if project_scope and project_scope.lower() not in haystack:
            continue
        if not needle or needle in haystack:
            results.append(
                {
                    "type": "knowledge",
                    "id": answer["answer_id"],
                    "project_id": None,
                    "title": answer.get("title")
                    or answer.get("subject")
                    or answer["answer_id"],
                    "ref": f"knowledge:{answer['answer_id']}",
                }
            )

    results, truncated = _bound_items(results, limit=cap)
    structured = {
        "query": query,
        "result_count": len(results),
        "truncated": truncated,
        "results": results,
        **INVARIANTS,
    }
    note = (
        f"Found {len(results)} Atlas reference(s) for {query!r} in the DEMO_FIXTURE estate. "
        "Search results are references, not proven claims."
    )
    return _seal(structured, note)


def _load_knowledge_document(vault: Path, answer_id: str) -> dict[str, Any] | None:
    """Load a bounded knowledge answer document (value + provenance pointers).

    Caps nested lists; never dumps unbounded vault inventory. Returns None when
    the answer file is absent or malformed.
    """
    path = vault / "generated" / "answers" / f"{answer_id}.json"
    raw = _load_json_object(path)
    if not raw:
        return None
    # Keep a provenance-bearing but bounded representation for ChatGPT inspection.
    value = raw.get("value")
    if isinstance(value, str) and len(value) > 4_096:
        value = value[:4_096] + "…[truncated]"
    provenance = raw.get("provenance") or raw.get("sources") or []
    if not isinstance(provenance, list):
        provenance = []
    provenance, prov_trunc = _bound_items(
        [p for p in provenance if isinstance(p, dict)],
        limit=MAX_RESULTS,
    )
    return {
        "answer_id": str(raw.get("answer_id") or answer_id),
        "subject": raw.get("subject"),
        "field": raw.get("field"),
        "value": value,
        "has_value": value is not None,
        "provenance": provenance,
        "truncated": prov_trunc,
        "path": f"generated/answers/{answer_id}.json",
        "note": "Knowledge document pointer — evidence is not interpretation; not authority.",
    }


def _knowledge_matches_project(answer: dict[str, Any], project_id: str) -> bool:
    """Best-effort project scope: subject/path/answer_id contain the project id."""
    needle = project_id.lower()
    haystack = " ".join(
        str(part)
        for part in (
            answer.get("answer_id"),
            answer.get("subject"),
            answer.get("field"),
            answer.get("path"),
            answer.get("title"),
            answer.get("summary"),
        )
        if part
    ).lower()
    return needle in haystack


def fetch(vault: Path, ref: str) -> ToolResult:
    """Return the complete Atlas representation for a reference. READ ONLY."""
    if not isinstance(ref, str) or ":" not in ref:
        raise GatewayError("ref must be '<type>:<id>' (e.g. 'project:harbor-api')")
    kind, _, ident = ref.partition(":")
    kind = kind.strip().lower()
    ident = ident.strip()

    if kind == "project":
        return atlas_project_status(vault, ident)

    if kind == "knowledge":
        for answer in list_knowledge_answers(vault):
            if answer["answer_id"] == ident:
                doc = _load_knowledge_document(vault, ident) or {
                    **answer,
                    "note": "Summary only — full answer document absent.",
                }
                return _seal(
                    {"kind": "knowledge", "found": True, "answer": doc, **INVARIANTS},
                    f"Knowledge reference {ident} (DEMO_FIXTURE). Evidence is not interpretation.",
                )
        return _not_found("knowledge", ident)

    if kind in {"claim", "conflict"}:
        index = _load_index(vault, {"claim": "claims", "conflict": "conflicts"}[kind])
        ids = index.get("ids")
        present = isinstance(ids, list) and ident in ids
        structured = {
            "kind": kind,
            "id": ident,
            "found": present,
            "note": "Reference pointer only — not a proven claim or interpretation."
            if present
            else "UNKNOWN — not present in DEMO_FIXTURE indexes.",
            **INVARIANTS,
        }
        narration = (
            f"{kind} {ident}: {'present' if present else 'UNKNOWN (absent)'} in DEMO_FIXTURE."
        )
        return _seal(structured, narration)

    if kind == "evidence":
        # Production provenance.json has by_source_lineage_id / by_receipt_id, not ids.
        index = _load_index(vault, "provenance")
        by_lineage = index.get("by_source_lineage_id")
        present = isinstance(by_lineage, dict) and ident in by_lineage
        lineages: list[str] = []
        lineages_truncated = False
        if present:
            # Never dump vault-wide lineage inventory for a single evidence id.
            lineages, lineages_truncated = _bound_items([ident])
        structured = {
            "kind": "evidence",
            "id": ident,
            "found": present,
            "provenance_lineages": lineages,
            "truncated": lineages_truncated,
            "note": "Reference/evidence pointer only — not a proven claim or interpretation."
            if present
            else "UNKNOWN — not present in DEMO_FIXTURE provenance lineages.",
            **INVARIANTS,
        }
        narration = (
            f"evidence {ident}: {'present' if present else 'UNKNOWN (absent)'} in DEMO_FIXTURE."
        )
        return _seal(structured, narration)

    if kind == "receipt":
        # Receipts live under provenance by_receipt_id (not authority.ids).
        index = _load_index(vault, "provenance")
        by_receipt = index.get("by_receipt_id")
        present = isinstance(by_receipt, dict) and ident in by_receipt
        linked, linked_trunc = _bound_items(
            list(by_receipt.get(ident, [])) if present and isinstance(by_receipt, dict) else []
        )
        structured = {
            "kind": "receipt",
            "id": ident,
            "found": present,
            "linked_record_ids": linked,
            "truncated": linked_trunc,
            "note": "Receipt pointer only — not a proven claim or interpretation."
            if present
            else "UNKNOWN — receipt id absent from DEMO_FIXTURE provenance.",
            **INVARIANTS,
        }
        narration = (
            f"receipt {ident}: {'present' if present else 'UNKNOWN (absent)'} in DEMO_FIXTURE."
        )
        return _seal(structured, narration)

    raise GatewayError(f"unsupported ref type: {kind!r}")


def _not_found(kind: str, ident: str) -> ToolResult:
    return _seal(
        {
            "kind": kind,
            "id": ident,
            "found": False,
            "note": "UNKNOWN — absent in DEMO_FIXTURE.",
            **INVARIANTS,
        },
        f"{kind} {ident} is UNKNOWN (absent) in the DEMO_FIXTURE estate — not fabricated.",
    )


def atlas_project_status(vault: Path, project_id: str) -> ToolResult:
    """Project status for a status card. READ ONLY."""
    if not isinstance(project_id, str) or not project_id:
        raise GatewayError("project_id is required")
    projects = {p["project_id"]: p for p in list_projects(vault)}
    if project_id not in projects:
        return _not_found("project", project_id)

    knowledge = [
        a for a in list_knowledge_answers(vault) if _knowledge_matches_project(a, project_id)
    ]
    knowledge_count = len(knowledge)
    concept_count = _count_for_project(vault, "concepts", project_id)
    conflict_count = _count_for_project(vault, "conflicts", project_id)
    evidence_count = _evidence_count(vault, project_id)
    edges = _dependency_edges(vault)
    dependencies, deps_trunc = _bound_items(edges.get(project_id, []))
    dependents, dent_trunc = _bound_items(
        sorted(pid for pid, targets in edges.items() if project_id in targets)
    )
    unknowns, unk_trunc = _bound_items(
        _unknowns(vault, project_id, knowledge_count, conflict_count)
    )

    structured = {
        "project": project_id,
        "has_project_note": projects[project_id].get("has_project_note", False),
        "state": "unknown",  # Objective: no lifecycle authority asserted here.
        "concept_count": concept_count,
        "knowledge_count": knowledge_count,
        "conflict_count": conflict_count,
        "evidence_count": evidence_count,
        "dependencies": dependencies,
        "dependents": dependents,
        "unknowns": unknowns,
        "truncated": deps_trunc or dent_trunc or unk_trunc,
        **INVARIANTS,
    }
    narration = (
        f"Project {project_id} (DEMO_FIXTURE): {concept_count} concept(s), "
        f"{knowledge_count} compiled answer(s), {conflict_count} detected conflict(s), "
        f"{evidence_count} evidence lineage(s), depends on {dependencies or 'none'}. "
        f"UNKNOWNs: {unknowns or 'none'}. Model narration is not Atlas authority."
    )
    return _seal(structured, narration, meta={"project_id": project_id})


def atlas_graph_neighbors(vault: Path, project_id: str) -> ToolResult:
    """Derived graph neighbors. READ ONLY. GRAPH != AUTHORITY."""
    if not isinstance(project_id, str) or not project_id:
        raise GatewayError("project_id is required")
    if project_id not in set(_project_ids(vault)):
        return _not_found("project", project_id)
    edges = _dependency_edges(vault)
    full_deps = edges.get(project_id, [])
    full_dents = sorted(pid for pid, targets in edges.items() if project_id in targets)
    dependencies, deps_trunc = _bound_items(full_deps)
    dependents, dent_trunc = _bound_items(full_dents)
    related, rel_trunc = _bound_items(sorted(set(full_deps) | set(full_dents)))
    structured = {
        "node": project_id,
        "dependencies": dependencies,
        "dependents": dependents,
        "related_projects": related,
        "truncated": deps_trunc or dent_trunc or rel_trunc,
        "edge_source": "portfolio/dependency-report.json (derived projection)",
        "note": "GRAPH != AUTHORITY — derived relationships never pick claim winners.",
        **INVARIANTS,
    }
    narration = (
        f"{project_id} derived neighbors (DEMO_FIXTURE): depends on {dependencies or 'none'}; "
        f"depended on by {dependents or 'none'}. Graph is derived, not authority."
    )
    return _seal(structured, narration, meta={"project_id": project_id})


# --------------------------------------------------------------------------- #
# Tool registry (consumed by the MCP server and tests)
# --------------------------------------------------------------------------- #

_READONLY_ANNOTATIONS: dict[str, Any] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": False,  # bounded to our own DEMO_FIXTURE vault
    "idempotentHint": True,
}

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "search": {
        "title": "Search Atlas",
        "description": "Locate Atlas projects/knowledge references for a query (READ ONLY, DEMO_FIXTURE).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text query."},
                "project_scope": {"type": "string", "description": "Restrict to one project id."},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTS},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": _READONLY_ANNOTATIONS,
        "outputTemplate": "ui://widget/atlas-card.html",
    },
    "fetch": {
        "title": "Fetch Atlas object",
        "description": "Fetch the full Atlas representation for a '<type>:<id>' reference (READ ONLY).",
        "inputSchema": {
            "type": "object",
            "properties": {"ref": {"type": "string", "description": "e.g. 'project:harbor-api'."}},
            "required": ["ref"],
            "additionalProperties": False,
        },
        "annotations": _READONLY_ANNOTATIONS,
        "outputTemplate": "ui://widget/atlas-card.html",
    },
    "atlas_project_status": {
        "title": "Atlas project status",
        "description": "Project status: concepts, knowledge, conflicts, evidence, dependencies, unknowns (READ ONLY).",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
        "annotations": _READONLY_ANNOTATIONS,
        "outputTemplate": "ui://widget/atlas-card.html",
    },
    "atlas_graph_neighbors": {
        "title": "Atlas graph neighbors",
        "description": "Derived dependency neighbors for a project (READ ONLY; GRAPH != AUTHORITY).",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
        "annotations": _READONLY_ANNOTATIONS,
        "outputTemplate": "ui://widget/atlas-card.html",
    },
}


def call_tool(vault: Path, name: str, arguments: dict[str, Any]) -> ToolResult:
    """Dispatch a read-only tool by name (used by the MCP server and tests)."""
    args = arguments or {}
    if name == "search":
        return search(vault, args.get("query", ""), args.get("project_scope"), args.get("limit"))
    if name == "fetch":
        return fetch(vault, args.get("ref", ""))
    if name == "atlas_project_status":
        return atlas_project_status(vault, args.get("project_id", ""))
    if name == "atlas_graph_neighbors":
        return atlas_graph_neighbors(vault, args.get("project_id", ""))
    raise GatewayError(f"unknown tool: {name!r}")
