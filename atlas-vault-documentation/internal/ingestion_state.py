"""Incremental ingestion state and explicit document lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

STATE_SCHEMA_VERSION = 1


def load_state(path: Path, project_id: str) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": STATE_SCHEMA_VERSION, "project_id": project_id, "documents": {}, "last_inventory_sha256": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError(f"unsupported ingestion state schema: {path}")
    return cast(dict[str, Any], data)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def diff_inventory(inventory: dict[str, Any], previous: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    current = {str(item["document_id"]): item for item in inventory.get("documents", [])}
    old = previous.get("documents", {}) if isinstance(previous.get("documents", {}), dict) else {}
    added: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    for document_id in sorted(current):
        item = current[document_id]
        prior = old.get(document_id)
        if prior is None:
            added.append(item)
        elif prior.get("sha256") != item.get("sha256"):
            changed.append(item)
        else:
            unchanged.append(item)
    deleted = [dict(value, processing=dict(value.get("processing", {}), state="deleted")) for key, value in sorted(old.items()) if key not in current]
    renamed: list[dict[str, Any]] = []
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for item in added:
        if item.get("sha256"):
            by_hash.setdefault(str(item["sha256"]), []).append(item)
    remaining_deleted: list[dict[str, Any]] = []
    remaining_added = list(added)
    for old_item in deleted:
        candidates = by_hash.get(str(old_item.get("sha256")), [])
        candidate = next((item for item in candidates if item in remaining_added), None)
        if candidate is None:
            remaining_deleted.append(old_item)
            continue
        remaining_added.remove(candidate)
        renamed.append({"from": old_item, "to": candidate, "basis": "identical-content-sha256"})
    return {"new": remaining_added, "changed": changed, "unchanged": unchanged, "deleted": remaining_deleted, "renamed": renamed}


def apply_inventory(state: dict[str, Any], inventory: dict[str, Any], diff: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    documents = dict(state.get("documents", {}))
    for item in diff["new"] + diff["changed"]:
        old = documents.get(str(item["document_id"]), {})
        documents[str(item["document_id"])] = {
            "document_id": item["document_id"], "relative_path": item["relative_path"],
            "sha256": item["sha256"], "previous_sha256": old.get("sha256"),
            "first_seen": old.get("first_seen", item["modified_time"]),
            "last_seen": item["modified_time"], "last_changed": item["modified_time"],
            "revision_count": int(old.get("revision_count", 0)) + 1,
            "state": "discovered", "route_event_ids": old.get("route_event_ids", []),
        }
    for item in diff["unchanged"]:
        record = dict(documents.get(str(item["document_id"]), {}))
        record["last_seen"] = item["modified_time"]
        record["state"] = "unchanged"
        documents[str(item["document_id"])] = record
    for item in diff["deleted"]:
        record = dict(documents.get(str(item["document_id"]), item))
        record["state"] = "deleted"
        record["last_seen"] = None
        documents[str(item["document_id"])] = record
    for rename in diff.get("renamed", []):
        old_item = rename["from"]
        new_item = rename["to"]
        old_id = str(old_item["document_id"])
        new_id = str(new_item["document_id"])
        record = dict(documents.get(old_id, old_item))
        history = list(record.get("path_history", []))
        if record.get("relative_path") not in history:
            history.append(record.get("relative_path"))
        history.append(new_item["relative_path"])
        record.update({"document_id": new_id, "relative_path": new_item["relative_path"], "last_seen": new_item["modified_time"], "state": "renamed", "path_history": history, "rename_basis": rename["basis"]})
        documents.pop(old_id, None)
        documents[new_id] = record
    state["documents"] = documents
    state["last_inventory_sha256"] = inventory["inventory_sha256"]
    return state
