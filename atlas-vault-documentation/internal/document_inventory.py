"""Deterministic, source-preserving document inventories."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from internal import authority_model, content_fingerprint, document_classifier, project_markers

SECRET_NAMES = {".env", "credentials.json", "id_rsa", "id_ed25519"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def _sensitivity(path: Path) -> tuple[str, bool]:
    name = path.name.lower()
    if name in SECRET_NAMES or name.startswith(".env.") or name.startswith("secrets.") or name.endswith(SECRET_SUFFIXES):
        return "sensitive", True
    return "normal", False


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _excluded(relative: str, config: dict[str, Any]) -> str | None:
    parts = set(relative.split("/"))
    if parts & project_markers.DEFAULT_EXCLUDED_DIRS:
        return "default-excluded-directory"
    inventory = config.get("inventory", {}) if isinstance(config.get("inventory", {}), dict) else {}
    excludes = inventory.get("exclude", []) if isinstance(inventory.get("exclude", []), list) else []
    from fnmatch import fnmatch
    for pattern in excludes:
        if fnmatch(relative, str(pattern)):
            return "configured-exclusion"
    return None


def inventory_project(project_root: Path, *, project_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    inventory_config = config.get("inventory", {}) if isinstance(config.get("inventory", {}), dict) else {}
    max_bytes = int(inventory_config.get("max_file_bytes", 5 * 1024 * 1024))
    records: list[dict[str, Any]] = []
    root = project_root.expanduser().resolve()
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not project_markers.is_excluded_dir(name))
        for filename in sorted(files):
            path = Path(current) / filename
            relative = path.relative_to(root).as_posix()
            excluded = _excluded(relative, config)
            if excluded:
                continue
            if path.is_symlink():
                records.append({
                    "document_id": f"{project_id}:{relative}", "project_id": project_id,
                    "relative_path": relative, "filename": filename,
                    "extension": path.suffix.lower(), "media_type": "application/octet-stream",
                    "size_bytes": 0, "modified_time": _mtime(path), "sha256": "",
                    "classification": {"type": "unknown", "confidence": "low", "evidence": ["symlink"], "competing": [], "rule_version": "1"},
                    "authority": authority_model.assign_authority(relative, config=config),
                    "processing": {"eligibility": "excluded", "handler": "none", "state": "quarantined", "reason": "symlink-not-followed"},
                    "security": {"sensitivity": "normal", "redaction_required": False},
                })
                continue
            size = path.stat().st_size
            media = document_classifier.media_type(path)
            sensitivity, redaction = _sensitivity(path)
            record: dict[str, Any] = {
                "document_id": f"{project_id}:{relative}",
                "project_id": project_id,
                "relative_path": relative,
                "filename": filename,
                "extension": path.suffix.lower(),
                "media_type": media or "application/octet-stream",
                "size_bytes": size,
                "modified_time": _mtime(path),
                "sha256": "",
                "classification": {"type": "unknown", "confidence": "low", "evidence": [], "competing": [], "rule_version": "1"},
                "authority": authority_model.assign_authority(relative, config=config),
                "processing": {"eligibility": "eligible", "handler": "text" if media else "inventory-only", "state": "discovered"},
                "security": {"sensitivity": sensitivity, "redaction_required": redaction},
            }
            if size > max_bytes:
                record["processing"] = {"eligibility": "excluded", "handler": "none", "state": "unsupported", "reason": "max-file-bytes-exceeded"}
            elif sensitivity == "sensitive":
                record["processing"] = {"eligibility": "excluded", "handler": "metadata-only", "state": "sensitive", "reason": "sensitive-filename"}
            try:
                record["sha256"] = content_fingerprint.sha256_file(path)
                if media and sensitivity == "normal" and size <= max_bytes:
                    try:
                        text = path.read_text(encoding="utf-8")
                    except UnicodeError:
                        record["processing"] = {"eligibility": "excluded", "handler": "none", "state": "unsupported", "reason": "invalid-utf8"}
                    else:
                        record["classification"] = document_classifier.classify(relative, text=text)
                elif not media and sensitivity == "normal":
                    record["processing"] = {"eligibility": "excluded", "handler": "inventory-only", "state": "unsupported", "reason": "unsupported-semantic-converter"}
                    if "graphify-out" in relative.lower():
                        record["classification"] = document_classifier.classify(relative)
                if record["classification"]["type"] == "graphify-output":
                    record["processing"] = {"eligibility": "excluded", "handler": "inventory-only", "state": "unsupported", "reason": "semantic-ingestion-deferred"}
            except OSError as exc:
                record["processing"] = {"eligibility": "excluded", "handler": "none", "state": "failed", "reason": type(exc).__name__}
            records.append(record)
    records.sort(key=lambda item: str(item["relative_path"]).casefold())
    return {
        "schema_version": 1,
        "project_id": project_id,
        "project_root": str(root),
        "documents": records,
        "inventory_sha256": content_fingerprint.inventory_hash(records),
    }


def serialize_inventory(inventory: dict[str, Any]) -> str:
    return json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
