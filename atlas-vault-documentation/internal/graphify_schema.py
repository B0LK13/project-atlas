"""Strict, bounded Graphify schema recognition."""

from __future__ import annotations

from typing import Any

SUPPORTED_SCHEMA = "graphify-1.0"
RELATIONSHIP_TYPES = {"part-of", "contains", "depends-on", "implements", "documents", "validates", "tests", "references", "supersedes", "blocks", "owned-by", "generated-by", "configured-by", "deployed-to", "stores-data-in", "exposes", "consumes", "invokes", "produces", "requires", "relates-to", "derived-from", "supports", "conflicts-with"}


class GraphSchemaError(ValueError):
    """Unsupported or malformed Graphify input."""


def schema_for(value: Any) -> str:
    if isinstance(value, dict) and value.get("schema_version") in (1, "1", "1.0", "graphify-1.0"):
        return SUPPORTED_SCHEMA
    if isinstance(value, dict) and ("nodes" in value or "edges" in value):
        return SUPPORTED_SCHEMA
    raise GraphSchemaError("unknown-schema")


def validate_record(value: Any, *, kind: str) -> None:
    if not isinstance(value, dict):
        raise GraphSchemaError("malformed-record")
    if kind == "node" and not (value.get("id") or value.get("node_id")):
        raise GraphSchemaError("node-missing-id")
    if kind == "edge" and not ((value.get("source") or value.get("from")) and (value.get("target") or value.get("to"))):
        raise GraphSchemaError("edge-missing-endpoint")
