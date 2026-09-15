"""Deterministic ingestion plans."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_plan(inventory: dict[str, Any], diff: dict[str, list[dict[str, Any]]], *, incremental: bool = True) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    for item in diff["new"]:
        eligible = item["processing"]["eligibility"] == "eligible"
        operations.append({"document_id": item["document_id"], "action": "ingest" if eligible else "inventory-only", "reason": "new-document", "capture": eligible, "normalize": eligible, "route": eligible})
    for item in diff["changed"]:
        eligible = item["processing"]["eligibility"] == "eligible"
        operations.append({"document_id": item["document_id"], "action": "ingest" if eligible else "inventory-only", "reason": "changed-document", "capture": eligible, "normalize": eligible, "route": eligible})
    for item in diff["unchanged"]:
        operations.append({"document_id": item["document_id"], "action": "retain", "reason": "unchanged", "capture": False, "normalize": False, "route": False})
    for item in diff["deleted"]:
        operations.append({"document_id": item["document_id"], "action": "retain", "reason": "source-missing", "capture": False, "normalize": False, "route": False})
    for rename in diff.get("renamed", []):
        operations.append({"document_id": rename["to"]["document_id"], "action": "rename", "reason": rename["basis"], "from_document_id": rename["from"]["document_id"], "capture": False, "normalize": False, "route": False})
    operations.sort(key=lambda item: str(item["document_id"]))
    plan = {"schema_version": 1, "project_id": inventory["project_id"], "inventory_sha256": inventory["inventory_sha256"], "incremental": incremental, "operations": operations}
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    plan["plan_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return plan
