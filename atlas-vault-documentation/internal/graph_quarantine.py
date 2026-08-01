"""Safe quarantine records for invalid Graphify nodes and edges."""

from __future__ import annotations

import hashlib
from typing import Any


def record(project_id: str, category: str, raw: dict[str, Any], *, artifact_id: str, message: str) -> dict[str, Any]:
    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items() if str(key).lower() not in {"secret", "token", "password", "content", "private_key"}}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    safe = redact(raw)
    fingerprint = hashlib.sha256(repr(sorted(safe.items())).encode("utf-8")).hexdigest()
    return {"schema_version": 1, "project_id": project_id, "status": "quarantined", "category": category, "message": message[:500], "record_fingerprint": fingerprint, "provenance": {"graphify_artifact_id": artifact_id}, "record": safe, "remediation": "review mapping or source artifact and retry"}
