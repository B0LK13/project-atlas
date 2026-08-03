"""Deterministic portfolio intelligence projections (AS-MVP-001).

Portfolio intelligence is strictly derived, regenerable, read-only toward
canonical records, and non-authoritative (Layer C of the three-layer vault
model, `docs/plan.md`). This module never writes to ``state/``,
``projects/``, ``sources/``, ``receipts/``, or any existing
``generated/indexes/*.json`` file; it only reads them and writes new,
additive output under ``generated/portfolio/``.

Data flow::

    canonical source/project state (state/*, review/conflicts/*,
    generated/reports/ingestion-report.json)
      -> deterministic portfolio projection (this module, pure functions)
        -> generated/portfolio/*.json + generated/navigation/portfolio-overview.md

Every entry in every generated file cites the source record (project id,
source id, claim id, concept id, or conflict id) it was derived from.
Absent or ambiguous evidence is reported as ``"unknown"``; nothing is
inferred from prose (I-007, I-008).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_atlas.ingestion import _promote
from project_atlas.semantic_compiler import COVERAGE_RULES, coverage_for

GENERATED_PORTFOLIO_ROOT = "generated/portfolio"
DEFAULT_STALE_DAYS = 180

# Coverage categories a project must satisfy for a "high maturity" signal;
# mirrors the "partial on a single match" categories in semantic_compiler.py.
_REQUIRED_COVERAGE_CATEGORIES = ("overview", "architecture", "security")

_RUNTIME_DEPENDENCY_CLAIM_TYPE = "runtime-dependency"
_CAPABILITY_CONCEPT_TYPE = "Capability"


def _json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def _state_records(vault: Path, directory: str, key: str) -> dict[str, list[dict[str, Any]]]:
    """Return {project_id: [record, ...]} for a per-project state directory."""
    root = vault / "state" / directory
    result: dict[str, list[dict[str, Any]]] = {}
    if not root.is_dir():
        return result
    for path in sorted(root.glob("*.json")):
        project_id = path.stem
        raw = _json(path, {})
        items = raw.get(key, []) if isinstance(raw, dict) else []
        result[project_id] = [item for item in items if isinstance(item, dict)]
    return result


def _manifest_sources(vault: Path) -> list[dict[str, Any]]:
    """Best-effort discovery-time manifest snapshot (all discovered sources).

    Known limitation: ``sources/manifests/source-manifest.json`` is
    overwritten by each ``atlas ingest`` call rather than merged, so it only
    reflects the most recently ingested discovery batch. A combined
    ``atlas discover``/``atlas ingest`` over every project (the recommended
    portfolio workflow) keeps this accurate for the whole vault.
    """
    raw = _json(vault / "sources" / "manifests" / "source-manifest.json", {"sources": []})
    return [item for item in raw.get("sources", []) if isinstance(item, dict)]


def _classifications(vault: Path) -> dict[str, str]:
    report = _json(vault / "generated" / "reports" / "ingestion-report.json", {})
    classifications = report.get("classifications", {}) if isinstance(report, dict) else {}
    return {
        str(source_id): str(info.get("type", ""))
        for source_id, info in classifications.items()
        if isinstance(info, dict)
    }


def _sources_state(vault: Path) -> dict[str, dict[str, Any]]:
    raw = _json(vault / "state" / "sources.json", {"sources": []})
    return {
        str(item["source_id"]): item
        for item in raw.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }


def _quarantined_source_ids(vault: Path) -> dict[str, dict[str, Any]]:
    """Metadata-only quarantine findings, keyed by source_id.

    Never reads matched text; only the existing safe fields
    (rule, confidence, disposition) that ``injection-findings.json`` and
    ``secret-findings.json`` already restrict themselves to (AS-SEC-001).
    """
    result: dict[str, dict[str, Any]] = {}
    for name in ("injection-findings.json", "secret-findings.json"):
        raw = _json(vault / "generated" / "reports" / name, {})
        for finding in raw.get("findings", []) if isinstance(raw, dict) else []:
            if not isinstance(finding, dict):
                continue
            source_id = str(finding.get("source_id", ""))
            if not source_id:
                continue
            result.setdefault(source_id, {"rules": [], "report": name})
            rule = finding.get("rule")
            if rule and rule not in result[source_id]["rules"]:
                result[source_id]["rules"].append(rule)
    return result


def _project_ids(vault: Path) -> list[str]:
    """Canonical project set: union of compiled concepts and projects/ dirs."""
    ids = set(_state_records(vault, "concepts", "concepts"))
    projects_root = vault / "projects"
    if projects_root.is_dir():
        ids.update(p.name for p in projects_root.iterdir() if p.is_dir())
    return sorted(ids)


def _project_source_ids(vault: Path, project_id: str, concepts: list[dict[str, Any]]) -> set[str]:
    """Source IDs belonging to a project, from its compiled concept sources."""
    result: set[str] = set()
    for concept in concepts:
        for source in concept.get("sources", []):
            if isinstance(source, dict) and source.get("source_id"):
                result.add(str(source["source_id"]))
    return result


def _project_manifest_source_ids(
    manifest_sources: list[dict[str, Any]], project_id: str
) -> set[str]:
    return {
        str(entry["source_id"])
        for entry in manifest_sources
        if entry.get("likely_project") == project_id and entry.get("source_id")
    }


def _coverage_entries_for_project(
    vault: Path, project_id: str, concepts: list[dict[str, Any]], classifications: dict[str, str]
) -> list[dict[str, Any]]:
    source_ids = _project_source_ids(vault, project_id, concepts)
    return [
        {"source_id": source_id, "classification": classifications.get(source_id, "")}
        for source_id in sorted(source_ids)
        if source_id in classifications
    ]


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _project_conflicts(vault: Path) -> dict[str, list[dict[str, Any]]]:
    root = vault / "review" / "conflicts"
    result: dict[str, list[dict[str, Any]]] = {}
    if not root.is_dir():
        return result
    for path in sorted(root.glob("*.json")):
        raw = _json(path, {})
        for entry in raw.get("entries", []) if isinstance(raw, dict) else []:
            if isinstance(entry, dict) and entry.get("project_id"):
                result.setdefault(str(entry["project_id"]), []).append(entry)
    return result


def documentation_coverage(vault: Path) -> dict[str, Any]:
    """I-004: portfolio-wide documentation coverage, aggregating the
    existing per-project ``coverage_for()`` output (semantic_compiler.py).
    Does not recompute coverage rules; reuses the certified category list
    and state literals (absent/partial/present/stale/conflicting)."""
    concepts_by_project = _state_records(vault, "concepts", "concepts")
    classifications = _classifications(vault)
    projects: dict[str, Any] = {}
    for project_id in _project_ids(vault):
        entries = _coverage_entries_for_project(
            vault, project_id, concepts_by_project.get(project_id, []), classifications
        )
        records = coverage_for(entries)
        projects[project_id] = {
            "categories": sorted(
                (
                    {
                        "category": record.category,
                        "state": record.state,
                        "source_ids": record.source_ids,
                    }
                    for record in records
                ),
                key=lambda item: item["category"],
            )
        }
    return {
        "schema_version": 1,
        "categories": [category for category, _ in COVERAGE_RULES],
        "projects": projects,
    }


def overview(vault: Path, coverage_payload: dict[str, Any]) -> dict[str, Any]:
    """I-002: stable, per-project portfolio summary."""
    conflicts_by_project = _project_conflicts(vault)
    manifest_sources = _manifest_sources(vault)
    quarantine = _quarantined_source_ids(vault)
    projects: list[dict[str, Any]] = []
    for project_id in _project_ids(vault):
        categories = coverage_payload["projects"].get(project_id, {}).get("categories", [])
        present = sum(1 for item in categories if item["state"] == "present")
        project_manifest_ids = _project_manifest_source_ids(manifest_sources, project_id)
        quarantined_count = sum(1 for sid in project_manifest_ids if sid in quarantine)
        projects.append(
            {
                "project_id": project_id,
                "coverage_categories_present": present,
                "coverage_categories_total": len(categories),
                "open_conflicts": len(conflicts_by_project.get(project_id, [])),
                "quarantined_sources": quarantined_count
                if manifest_sources
                else "unknown",
            }
        )
    return {
        "schema_version": 1,
        "project_count": len(projects),
        "projects": sorted(projects, key=lambda item: item["project_id"]),
    }


def maturity_matrix(vault: Path, coverage_payload: dict[str, Any]) -> dict[str, Any]:
    """I-003: categorical maturity, reusing the existing Maturity enum on
    each project's compiled concept. No numeric score: every entry cites
    the explicit inputs it was derived from (all themselves direct reads
    of canonical/generated values, never inferred)."""
    concepts_by_project = _state_records(vault, "concepts", "concepts")
    conflicts_by_project = _project_conflicts(vault)
    projects: dict[str, Any] = {}
    for project_id in _project_ids(vault):
        concepts = concepts_by_project.get(project_id, [])
        project_concept = next(
            (c for c in concepts if c.get("concept_id") == project_id), None
        )
        declared_maturity = (
            project_concept.get("maturity") if project_concept else None
        )
        categories = coverage_payload["projects"].get(project_id, {}).get("categories", [])
        required_present = all(
            any(
                item["category"] == required and item["state"] in ("present", "partial")
                for item in categories
            )
            for required in _REQUIRED_COVERAGE_CATEGORIES
        )
        validation_present = any(
            item["category"] == "testing" and item["state"] == "present" for item in categories
        )
        open_conflicts = len(conflicts_by_project.get(project_id, []))
        projects[project_id] = {
            "maturity": declared_maturity or "unknown",
            "inputs": {
                "declared_maturity_source": f"state/concepts/{project_id}.json"
                if declared_maturity
                else None,
                "required_coverage_present": required_present,
                "validation_evidence_present": validation_present,
                "open_conflicts": open_conflicts,
            },
        }
    return {"schema_version": 1, "projects": projects}


def stale_knowledge(
    vault: Path, *, reference_date: datetime, stale_after_days: int = DEFAULT_STALE_DAYS
) -> dict[str, Any]:
    """I-005: staleness computed from the discovery-time manifest's
    ``modified_at`` field against an injected reference date (never the
    wall clock inside this function). A source with no known
    ``modified_at`` is reported as ``"unknown"``, never assumed fresh."""
    manifest_sources = _manifest_sources(vault)
    quarantined = _quarantined_source_ids(vault)
    findings: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest_sources:
        project_id = entry.get("likely_project")
        source_id = entry.get("source_id")
        if not project_id or not source_id:
            continue
        if str(source_id) in quarantined:
            # AS-SEC-001 boundary: quarantined sources may only surface as
            # safe aggregate counts (see overview()'s quarantined_sources),
            # never as an individually cited source_id/path here.
            continue
        modified_at = _parse_datetime(entry.get("modified_at"))
        if modified_at is None:
            freshness = "unknown"
        else:
            age_days = (reference_date - modified_at).days
            freshness = "stale" if age_days >= stale_after_days else "fresh"
        if freshness == "unknown":
            continue
        findings.setdefault(str(project_id), []).append(
            {
                "source_id": str(source_id),
                "path": str(entry.get("path", "")),
                "freshness": freshness,
                "modified_at": entry.get("modified_at"),
            }
        )
    for items in findings.values():
        items.sort(key=lambda item: item["source_id"])
    return {
        "schema_version": 1,
        "reference_date": reference_date.isoformat(),
        "stale_after_days": stale_after_days,
        "projects": {
            project_id: {
                "stale_count": sum(1 for item in items if item["freshness"] == "stale"),
                "sources": items,
            }
            for project_id, items in sorted(findings.items())
        },
    }


def dependency_report(vault: Path) -> dict[str, Any]:
    """I-007: declared runtime-dependency claims only (deterministic
    ``requires:``/``dependency:`` line extraction already performed by
    knowledge_compiler.py, AS-CORE-003). Nothing is inferred from prose;
    every entry cites the claim ID and its provenance."""
    claims_by_project = _state_records(vault, "claims", "claims")
    projects: dict[str, Any] = {}
    for project_id, claims in sorted(claims_by_project.items()):
        entries = [
            {
                "claim_id": claim.get("claim_id"),
                "target": claim.get("value"),
                "provenance": sorted(
                    (
                        {
                            "source_id": ref.get("source_id"),
                            "source_lineage_id": ref.get("source_lineage_id"),
                        }
                        for ref in claim.get("provenance", [])
                        if isinstance(ref, dict)
                    ),
                    key=lambda item: str(item["source_id"]),
                ),
            }
            for claim in claims
            if claim.get("claim_type") == _RUNTIME_DEPENDENCY_CLAIM_TYPE
        ]
        # Relationship-modeled dependencies (Relationship/RelationType on
        # ConceptRecord.relationships), included when present so this report
        # stays forward-compatible with richer concept generation
        # (backlog CORE-MODEL-001) without requiring it.
        concepts = _state_records(vault, "concepts", "concepts").get(project_id, [])
        for concept in concepts:
            for relationship in concept.get("relationships", []):
                if isinstance(relationship, dict) and relationship.get("type") in (
                    "depends_on",
                    "related_project",
                ):
                    entries.append(
                        {
                            "claim_id": None,
                            "concept_id": concept.get("concept_id"),
                            "target": relationship.get("target"),
                            "relationship_type": relationship.get("type"),
                        }
                    )
        if entries:
            projects[project_id] = sorted(
                entries, key=lambda item: (item.get("target") or "", item.get("claim_id") or "")
            )
    return {"schema_version": 1, "projects": projects}


def capability_report(vault: Path) -> dict[str, Any]:
    """I-008: capability concepts (ConceptType.CAPABILITY, explicitly
    declared via a source's ``concept_type`` classification) and any
    ``provides`` relationships already present on canonical concepts.
    Nothing is inferred from ordinary document wording."""
    concepts_by_project = _state_records(vault, "concepts", "concepts")
    projects: dict[str, Any] = {}
    for project_id, concepts in sorted(concepts_by_project.items()):
        capabilities = [
            {
                "concept_id": concept.get("concept_id"),
                "title": concept.get("title"),
                "tags": sorted(concept.get("tags", [])),
            }
            for concept in concepts
            if concept.get("type") == _CAPABILITY_CONCEPT_TYPE
        ]
        provides = [
            {
                "concept_id": concept.get("concept_id"),
                "target": relationship.get("target"),
            }
            for concept in concepts
            for relationship in concept.get("relationships", [])
            if isinstance(relationship, dict) and relationship.get("type") == "provides"
        ]
        if capabilities or provides:
            projects[project_id] = {
                "capabilities": sorted(capabilities, key=lambda item: str(item["concept_id"])),
                "provides": sorted(provides, key=lambda item: str(item["target"])),
            }
    return {"schema_version": 1, "projects": projects}


def build_portfolio_payloads(
    vault: Path, *, reference_date: datetime | None = None
) -> dict[str, dict[str, Any]]:
    """Compute every generated/portfolio/*.json payload (pure, read-only)."""
    reference_date = reference_date or datetime.now(UTC)
    coverage_payload = documentation_coverage(vault)
    return {
        "documentation-coverage.json": coverage_payload,
        "overview.json": overview(vault, coverage_payload),
        "maturity-matrix.json": maturity_matrix(vault, coverage_payload),
        "stale-knowledge.json": stale_knowledge(vault, reference_date=reference_date),
        "dependency-report.json": dependency_report(vault),
        "capability-report.json": capability_report(vault),
    }


def _navigation_markdown(payloads: dict[str, dict[str, Any]]) -> str:
    lines = ["# Portfolio overview", "", "Generated from canonical project projections.", ""]
    for entry in payloads["overview.json"]["projects"]:
        lines.append(
            f"- [{entry['project_id']}](../../projects/{entry['project_id']}/project.md) — "
            f"coverage {entry['coverage_categories_present']}/"
            f"{entry['coverage_categories_total']}, "
            f"open conflicts {entry['open_conflicts']}"
        )
    lines.append("")
    return "\n".join(lines)


def build_portfolio(vault: Path, *, reference_date: datetime | None = None) -> dict[str, Any]:
    """Build ``generated/portfolio/`` outputs through the certified
    promotion boundary. Read-only toward canonical state; deterministic
    for unchanged input (no wall-clock value is embedded in the
    deterministic JSON bodies beyond the caller-supplied reference date,
    which is exposed only inside stale-knowledge.json)."""
    vault = vault.expanduser().resolve()
    payloads = build_portfolio_payloads(vault, reference_date=reference_date)
    write_plan: dict[Path, bytes] = {
        vault / GENERATED_PORTFOLIO_ROOT / name: (
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        ).encode()
        for name, value in sorted(payloads.items())
    }
    write_plan[vault / "generated" / "navigation" / "portfolio-overview.md"] = (
        _navigation_markdown(payloads).encode()
    )
    _promote(write_plan)
    return {
        "ok": True,
        "projects": len(payloads["overview.json"]["projects"]),
        "outputs": sorted(name for name in payloads),
    }
