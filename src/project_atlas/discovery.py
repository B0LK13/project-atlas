"""Deterministic source discovery for the Atlas Core vertical slice."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from atlas_contracts.event_package import EventPackageInventory, inspect_event_package
from project_atlas.domain.sources import SourceRecord
from project_atlas.domain.vocabulary import ClassificationState
from project_atlas.source_identity import canonicalize_project_path, validate_project_uuid

SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html"}
SENSITIVE_NAMES = {".env", "credentials.json", "secrets.pem", "id_rsa", "id_ed25519"}
DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".tmp",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_context(path: Path, root: Path) -> tuple[str | None, str | None]:
    current = path.parent
    while True:
        for marker in (current / ".atlas-project.yaml", current / ".atlas" / "project.yaml"):
            if marker.is_file():
                data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
                value = data.get("project", {}).get("id") if isinstance(data, dict) else None
                raw_uuid = data.get("project_uuid") if isinstance(data, dict) else None
                project_uuid = None
                if raw_uuid is not None:
                    project_uuid = validate_project_uuid(str(raw_uuid))
                return (str(value) if isinstance(value, str) and value else None, project_uuid)
        if current == root or current.parent == current:
            return None, None
        current = current.parent


def _project_id(path: Path, root: Path) -> str | None:
    """Return the compatibility display/project scope identifier."""
    return _project_context(path, root)[0]


def _excluded(relative: str, path: Path, *, excludes: list[str]) -> str | None:
    if any(part in DEFAULT_EXCLUDES for part in PurePosixPath(relative).parts):
        return "default-excluded-directory"
    if any(
        PurePosixPath(relative).match(pattern) or fnmatch.fnmatch(relative, pattern)
        for pattern in excludes
    ):
        return "configured-exclusion"
    if path.name in SENSITIVE_NAMES or path.name.startswith(".env"):
        return "sensitive-metadata-only"
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return "unsupported-format"
    return None


def _discover_agent_events(root: Path) -> list[dict[str, Any]]:
    """Inventory Control Plane packages without importing its implementation."""
    inbox = root / ".atlas-inbox" / "agent-events"
    if not inbox.is_dir() or inbox.is_symlink():
        return []
    inventories: list[EventPackageInventory] = []
    for project_dir in sorted(inbox.iterdir(), key=lambda path: path.name.lower()):
        if not project_dir.is_dir():
            continue
        for event_dir in sorted(project_dir.iterdir(), key=lambda path: path.name.lower()):
            if not event_dir.is_dir():
                continue
            relative = event_dir.relative_to(root).as_posix()
            inventories.append(
                inspect_event_package(root, project_dir.name, event_dir.name, relative)
            )
    by_event_id: dict[str, list[EventPackageInventory]] = {}
    for inventory in inventories:
        by_event_id.setdefault(inventory.event_id, []).append(inventory)
    result: list[dict[str, Any]] = []
    for inventory in inventories:
        peers = by_event_id[inventory.event_id]
        if len(peers) > 1:
            hashes = [peer.component_sha256 for peer in peers]
            identical = bool(hashes[0]) and all(peer_hash == hashes[0] for peer_hash in hashes)
            inventory = inventory.model_copy(
                update={
                    "status": "valid" if identical else "conflicting",
                    "errors": [
                        *inventory.errors,
                        "identical duplicate event_id in inbox"
                        if identical
                        else "conflicting duplicate event_id in inbox",
                    ],
                }
            )
        result.append(inventory.model_dump(mode="json"))
    return result


def discover(
    root: Path,
    *,
    excludes: list[str] | None = None,
    max_file_size: int = 10 * 1024 * 1024,
) -> dict[str, Any]:
    """Discover files under ``root`` into a deterministic JSON manifest."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"source root is not a directory: {root}")
    records: list[dict[str, Any]] = []
    event_root = root / ".atlas-inbox" / "agent-events"
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or path.is_symlink():
            continue
        if event_root.is_dir() and path.is_relative_to(event_root):
            continue
        relative = path.relative_to(root).as_posix()
        reason = _excluded(relative, path, excludes=excludes or [])
        stat = path.stat()
        if reason is None and stat.st_size > max_file_size:
            reason = "oversized"
        canonical_relative = canonicalize_project_path(relative)
        source_id = "source-" + hashlib.sha256(canonical_relative.encode("utf-8")).hexdigest()[:16]
        digest = None if reason == "sensitive-metadata-only" else _sha256(path)
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        project_id, project_uuid = _project_context(path, root)
        source_record = SourceRecord(
            source_id=source_id,
            project_uuid=project_uuid,
            source_lineage_id=None,
            path=relative,
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            sha256=digest,
            size_bytes=stat.st_size,
            modified_at=modified,
            likely_project=project_id,
            classification_state=(
                ClassificationState.EXCLUDED if reason else ClassificationState.UNCLASSIFIED
            ),
            exclusion_reason=reason,
        )
        records.append(source_record.model_dump(mode="json"))
    groups: dict[str, list[str]] = {}
    for record in records:
        digest = record.get("sha256")
        if isinstance(digest, str):
            groups.setdefault(digest, []).append(str(record["source_id"]))
    duplicates = {digest: ids for digest, ids in sorted(groups.items()) if len(ids) > 1}
    semantic = {
        "schema_version": 1,
        "source_root": str(root),
        "sources": records,
        "duplicates": duplicates,
        "agent_events": _discover_agent_events(root),
    }
    inventory_hash = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    semantic["inventory_sha256"] = inventory_hash
    return semantic


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    """Atomically write a stable manifest."""
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if output.is_file() and output.read_text(encoding="utf-8") == content:
        return
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, output)
