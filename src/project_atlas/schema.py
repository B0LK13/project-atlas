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
