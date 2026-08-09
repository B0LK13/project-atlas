"""JSON schema loading and validation for domain records (B-007).

Schemas ship as package data under ``project_atlas/schemas`` so validation
works from an installed package without a repository checkout (ADR-001).
Each domain model can be validated against its canonical schema, keeping
the Pydantic models and the published JSON contract in lockstep.
"""

from __future__ import annotations

import json
from functools import cache, lru_cache
from importlib import resources
from typing import Any

import jsonschema
from pydantic import BaseModel
from referencing import Registry, Resource

_SCHEMA_PACKAGE = "project_atlas.schemas"

#: Maps record kind to its schema file name.
SCHEMA_FILES: dict[str, str] = {
    "source-record": "source-record.schema.json",
    "source-registry": "source-registry.schema.json",
    "concept-record": "concept-record.schema.json",
    "claim": "claim.schema.json",
    "provenance-reference": "provenance-reference.schema.json",
    "conflict-record": "conflict-record.schema.json",
    "authority-record": "authority-record.schema.json",
    "claim-lifecycle": "claim-lifecycle.schema.json",
    "review-entry": "review-entry.schema.json",
    "validation-finding": "validation-finding.schema.json",
    "semantic-records": "semantic-records.schema.json",
    "claim-alias": "claim-alias.schema.json",
    "parser-output": "parser-output.schema.json",
    "diagnostic": "diagnostic.schema.json",
    "knowledge-answer": "knowledge-answer.schema.json",
    "knowledge-multifield-answer": "knowledge-multifield-answer.schema.json",
    "query-diagnostic": "query-diagnostic.schema.json",
    # AS-QUERY-MULTI-001 — tip-safe multi-subject / multi-project PLAN (≠ answer / authority)
    "query-multi-plan": "query-multi-plan.schema.json",
    # AS-EXPLAIN-001 — explainability / provenance receipts (operational metadata ≠ authority)
    "explain-receipt": "explain-receipt.schema.json",
    # AS-EXPLAIN-001 Band B — graph explain sidecars (derived enrichment ≠ query winner)
    "explain-graph-sidecar": "explain-graph-sidecar.schema.json",
    # AS-GRAPH-001 — Graphify acceptance (derived-only; not domain authority)
    "graphify-envelope": "graphify-envelope.schema.json",
    "graphify-node": "graphify-node.schema.json",
    "graphify-edge": "graphify-edge.schema.json",
    "graphify-metadata": "graphify-metadata.schema.json",
    "graph-acceptance-receipt": "graph-acceptance-receipt.schema.json",
    # AS-GRAPH-002 — Deterministic entity resolution (derived-only; not authority)
    "graph-resolved-node": "graph-resolved-node.schema.json",
    "graph-identity-explanation": "graph-identity-explanation.schema.json",
    # AS-OBS-001 - operational health snapshot (non-authoritative ops plane)
    "ops-health-snapshot": "ops-health-snapshot.schema.json",
    # AS-OBS-002 - operational event stream (OPS-EVT-*; non-authoritative ops plane)
    "ops-event": "ops-event.schema.json",
    "ops-event-stream": "ops-event-stream.schema.json",
    # AS-OBS-003 - ops-report projection (consume OBS-001 snapshot; optional OBS-002 events)
    "ops-report": "ops-report.schema.json",
    # AS-GRAPH-003 - Canonical derived relationships (not authority; not CP relationships/)
    "graph-relationship": "graph-relationship.schema.json",
    "graph-relationship-quarantine": "graph-relationship-quarantine.schema.json",
    # AS-GRAPH-004 - Durable quarantine / health / incremental (derived; never authority)
    "graph-quarantine-record": "graph-quarantine-record.schema.json",
    "graph-quarantine-receipt": "graph-quarantine-receipt.schema.json",
    "graph-health-snapshot": "graph-health-snapshot.schema.json",
    "graph-incremental-state": "graph-incremental-state.schema.json",
    # AS-XPROJ-001 - Global entity identity registry (derived; not automatic authority)
    "xproj-global-entity": "xproj-global-entity.schema.json",
    "xproj-join-key": "xproj-join-key.schema.json",
    "xproj-quarantine-candidate": "xproj-quarantine-candidate.schema.json",
    # AS-XPROJ-002 - Cross-project edges between registered globals (derived; no name-merge)
    "xproj-global-edge": "xproj-global-edge.schema.json",
    "xproj-edge-quarantine": "xproj-edge-quarantine.schema.json",
    # AS-XPROJ-004 - Conflict intelligence + global derived indexes (derived; not RET-001)
    "xproj-conflict-report": "xproj-conflict-report.schema.json",
    "xproj-index-document": "xproj-index-document.schema.json",
    # AS-XPROJ-003 - Duplicate / successor review candidates (derived; no autocollapse)
    "xproj-duplicate-candidate": "xproj-duplicate-candidate.schema.json",

    # AS-BACKUP-001 — verified snapshot / restore (operational durability ≠ authority)
    "backup-manifest": "backup-manifest.schema.json",
    "backup-meta": "backup-meta.schema.json",
    "backup-receipt": "backup-receipt.schema.json",
    # AS-INCR-COMPILE-001 tip-safe compile-cache receipt (not authority/GRAPH/XPROJ)
    "compile-cache-receipt": "compile-cache-receipt.schema.json",
    # AS-INT-009 — raw package / receipt retention (operational; not authority)
    "event-retention-policy": "event-retention-policy.schema.json",
    "event-retention-report": "event-retention-report.schema.json",
    # AS-INT-010 — removed-package / deletion tombstone projection (operational)
    "event-tombstone-index": "event-tombstone-index.schema.json",
    # AS-INT-011 — receipt revocation / invalidation (operational; never authority)
    "receipt-revocation-index": "receipt-revocation-index.schema.json",
    # AS-INT-012 — schema compatibility / migration report (operational)
    "schema-compat-report": "schema-compat-report.schema.json",
    # AS-CORE2-010 — fixture-safe lifecycle certification (≠ estate PILOT PASS)
    "lifecycle-cert-report": "lifecycle-cert-report.schema.json",
    # AS-ADV-RELEASE-001 — recovery/determinism/perf fixture cert (≠ RELEASE CERTIFIED)
    "adv-release-cert-report": "adv-release-cert-report.schema.json",
    # AS-SYNC-001-SCAFFOLD — dry-run workspace registry (≠ production SYNC-001 / PILOT)
    "workspace-registry-dry-run": "workspace-registry-dry-run.schema.json",
    # AS-J-005 — derived impact graph projection (Graph≠authority; consume GRAPH-003)
    "impact-graph": "impact-graph.schema.json",
}


class SchemaValidationError(ValueError):
    """Raised when a record fails validation against its JSON schema."""


def available_schemas() -> list[str]:
    """Return the record kinds that have a shipped JSON schema."""
    return sorted(SCHEMA_FILES)


def _read_schema(file_name: str) -> dict[str, Any]:
    resource = resources.files(_SCHEMA_PACKAGE).joinpath(file_name)
    return json.loads(resource.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _registry() -> Registry[Any]:
    """Registry resolving cross-file ``$ref`` targets by schema ``$id``."""
    pairs = [
        (schema["$id"], Resource.from_contents(schema))
        for schema in (_read_schema(name) for name in SCHEMA_FILES.values())
    ]
    return Registry().with_resources(pairs)


@cache
def load_schema(kind: str) -> dict[str, Any]:
    """Load a shipped schema by record kind (e.g. ``source-record``)."""
    try:
        file_name = SCHEMA_FILES[kind]
    except KeyError:
        raise KeyError(f"unknown schema kind: {kind!r}; available: {available_schemas()}") from None
    schema = _read_schema(file_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validate_record(record: BaseModel | dict[str, Any], kind: str) -> None:
    """Validate a domain record against its shipped JSON schema.

    ``record`` may be a Pydantic model (dumped in JSON mode) or a plain
    mapping. Raises :class:`SchemaValidationError` on the first violation.
    """
    schema = load_schema(kind)
    instance = record.model_dump(mode="json") if isinstance(record, BaseModel) else record
    validator = jsonschema.Draft202012Validator(schema, registry=_registry())
    error = next(validator.iter_errors(instance), None)
    if error is not None:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise SchemaValidationError(
            f"{kind} record violates schema at {location}: {error.message}"
        )
