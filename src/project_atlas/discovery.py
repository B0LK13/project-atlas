"""Deterministic source discovery for the Atlas Core vertical slice."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from atlas_contracts.event_package import EventPackageInventory, inspect_event_package
from atlas_contracts.paths import safe_relative_path
from project_atlas.domain.sources import SourceRecord
from project_atlas.domain.vocabulary import ClassificationState
from project_atlas.logging import get_logger
from project_atlas.quarantine import scan_identifier
from project_atlas.source_identity import (
    TEXT_SOURCE_EXTENSIONS,
    canonical_source_sha256,
    canonicalize_project_path,
    validate_project_uuid,
)

_log = get_logger("discovery")

SUPPORTED_EXTENSIONS = TEXT_SOURCE_EXTENSIONS
SENSITIVE_NAMES = {".env", "credentials.json", "secrets.pem", "id_rsa", "id_ed25519"}
DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".tmp",
    # Coder Alpha / local dogfood: in-tree vault + bind metadata must never
    # re-enter discovery as project sources (AS-CODER-ALPHA-CONNECT-001).
    ".atlas-vault", ".atlas",
    # Dogfood/real estates: fixture corpora must not masquerade as live projects
    # when connecting a repository root (AS-CODER-ALPHA-WEB-001 dogfood).
    # Discovering a fixture directory itself as --source remains valid because
    # "fixtures" is then the root, not a relative path part.
    "fixtures",
}

# AS-CORE-003: static media-type map. mimetypes.guess_type() depends on the
# host OS mime database (Linux maps .yaml, Windows does not), which made
# manifest media_type platform-dependent and broke NFR-001 determinism.
_MEDIA_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".json": "application/json",
    ".md": "text/markdown",
    ".toml": "application/toml",
    ".txt": "text/plain",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


def _media_type(path: Path) -> str:
    """Return the deterministic media type for a discovered source file."""
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _sha256(path: Path) -> str:
    """Return the streaming canonical SHA-256 of a source file."""
    return canonical_source_sha256(path)


def _project_context(path: Path, root: Path) -> tuple[str | None, str | None]:
    current = path.parent
    while True:
        for marker in (current / ".atlas-project.yaml", current / ".atlas" / "project.yaml"):
            if marker.is_file():
                try:
                    data = yaml.safe_load(marker.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, yaml.YAMLError) as exc:
                    # D-057: controlled fail-closed — no raw YAML traceback.
                    raise ValueError(
                        f"INVALID_PROJECT_MARKER: invalid project marker YAML: "
                        f"{marker.relative_to(root)}"
                    ) from exc
                if data is None:
                    data = {}
                if not isinstance(data, dict):
                    raise ValueError(
                        f"INVALID_PROJECT_MARKER: project marker must be an object: "
                        f"{marker.relative_to(root)}"
                    )
                project_data = data.get("project")
                value = project_data.get("id") if isinstance(project_data, dict) else None
                raw_uuid = data.get("project_uuid")
                project_uuid = None
                if raw_uuid is not None:
                    project_uuid = validate_project_uuid(str(raw_uuid))
                if isinstance(value, str) and value:
                    findings = scan_identifier(value)
                    if findings:
                        raise ValueError(
                            f"adversarial project identifier in {marker.relative_to(root)}: "
                            f"{findings[0].rule} ({findings[0].redacted_hint})"
                        )
                    return str(value), project_uuid
                return None, project_uuid
        if current == root or current.parent == current:
            return None, None
        current = current.parent


def _project_id(path: Path, root: Path) -> str | None:
    """Return the compatibility display/project scope identifier."""
    return _project_context(path, root)[0]


def _compatibility_source_id(
    *,
    canonical_relative: str,
    project_id: str | None,
    root: Path,
) -> str:
    """Mint a vault-unique compatibility ``source_id`` (D-050 R3).

    Path-only IDs collide when multiple project roots share a vault and the same
    relative paths (``README.md``). Scope by governed ``project.id`` when the
    marker is present; otherwise by a stable fingerprint of the discover root.
    Durable lineage remains ``source_lineage_id`` (project UUID + path + SHA).
    """
    if isinstance(project_id, str) and project_id.strip():
        material = f"project:{project_id.strip()}|{canonical_relative}"
    else:
        root_fp = hashlib.sha256(
            root.resolve().as_posix().casefold().encode("utf-8")
        ).hexdigest()[:16]
        material = f"root:{root_fp}|{canonical_relative}"
    return "source-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


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


def _non_portable_reason(relative: str) -> str | None:
    """Reason a Linux-legal relative path cannot be represented portably.

    Linux permits names the shared path contract (CODEX-SEC-004/014/017/018)
    refuses on every platform: colons, control characters, Windows reserved
    basenames, trailing dots or spaces. A backslash is a legal Linux filename
    character too, but the contract reinterprets it as a separator, so the
    round trip must be lossless or the recorded path would name a different
    file than the one discovered. Such sources are recorded as excluded
    evidence here rather than failing the whole run closed at the ingest
    boundary, which is where they used to surface (a Linux-only dead end:
    discovery emitted a path ingestion could never accept).
    """
    try:
        segments = safe_relative_path(relative, label="source path")
    except ValueError:
        return "non-portable-path"
    if "/".join(segments) != relative:
        return "non-portable-path"
    return None


def _reportable(relative: str) -> str:
    """An ASCII-safe rendering of a path for log messages.

    Paths reaching the log may be undecodable (lone surrogates) or merely
    non-ASCII, and a diagnostic must never itself raise while reporting a
    problem. Encoding to ASCII (not UTF-8) is what escapes both: UTF-8 can
    encode an accented name happily, and the resulting bytes then fail an
    ASCII decode.
    """
    return relative.encode("ascii", "backslashreplace").decode("ascii")


def _is_listable(path: Path) -> bool:
    """True when this directory's entries can actually be enumerated.

    `Path.rglob` swallows the failure for a directory it cannot read, so an
    inaccessible subtree would otherwise vanish from the inventory with no
    record and no diagnostic. Probing here is what makes that loss
    observable.
    """
    try:
        with os.scandir(path) as entries:
            next(iter(entries), None)
    except OSError:
        return False
    return True


def _is_recordable(relative: str) -> bool:
    """False when a path cannot appear in the UTF-8 JSON manifest at all.

    Linux filenames are byte strings, not text. A name that is not valid
    UTF-8 decodes to lone surrogates (``surrogateescape``), which cannot be
    encoded back out -- it would break both the inventory hash and the
    manifest write, aborting the whole run over one file.
    """
    try:
        relative.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _discover_agent_events(root: Path) -> list[dict[str, Any]]:
    """Inventory Control Plane packages without importing its implementation."""
    inbox = root / ".atlas-inbox" / "agent-events"
    if not inbox.is_dir() or inbox.is_symlink():
        return []
    inventories: list[EventPackageInventory] = []
    for project_dir in sorted(inbox.iterdir(), key=lambda path: path.name.lower()):
        if not project_dir.is_dir():
            # AS-INT-001: only `<project-id>/<event-id>/` package directories
            # are valid here, and `discover()` excludes this whole subtree from
            # `sources` so package components are not double-counted as
            # ordinary documentation. A real file dropped in here therefore
            # reaches neither inventory -- it must not do so silently. No
            # source identity and no agent event are synthesized for it: it
            # has neither a project_id nor an event_id, and inventing either
            # would fabricate routed evidence.
            _log.warning(
                "unexpected non-package entry in reserved agent-event scope: %s "
                "(only <project-id>/<event-id>/ package directories are valid here)",
                _reportable(project_dir.relative_to(root).as_posix()),
            )
            continue
        for event_dir in sorted(project_dir.iterdir(), key=lambda path: path.name.lower()):
            if not event_dir.is_dir():
                _log.warning(
                    "unexpected non-package entry in reserved agent-event scope: %s "
                    "(only <project-id>/<event-id>/ package directories are valid here)",
                    _reportable(event_dir.relative_to(root).as_posix()),
                )
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
    seen_canonical: dict[str, str] = {}
    for path in sorted(
        root.rglob("*"),
        # The case-folded key alone ties on case variants (README.md vs
        # readme.md); a stable sort then inherits directory-entry order, so
        # the inventory hash depended on creation order (NFR-001). Appending
        # the raw path breaks every tie totally, which is also what makes
        # "first in deterministic order wins" true for collision handling.
        key=lambda item: (item.as_posix().lower(), item.as_posix()),
    ):
        relative = path.relative_to(root).as_posix()
        try:
            # The first metadata access, not `stat()` below: a directory that
            # lists but does not traverse (mode 0444) makes even is_file()
            # raise EACCES. One unreachable entry must never abort the run.
            regular_file = path.is_file() and not path.is_symlink()
            directory = path.is_dir() and not path.is_symlink()
        except OSError as exc:
            _log.warning(
                "skipped unreadable path: %s (%s)", _reportable(relative), exc.strerror
            )
            continue
        if directory and not _is_listable(path):
            # Evidence that a scope exists and could not be inspected. Its
            # contents are deliberately not invented -- they were never read.
            _log.warning(
                "inaccessible discovery scope, contents not inventoried: %s",
                _reportable(relative),
            )
            continue
        if not regular_file:
            continue
        if event_root.is_dir() and path.is_relative_to(event_root):
            continue
        if not _is_recordable(relative):
            # Reported rather than recorded: a sanitized path would be a
            # claim about a file that does not exist under that name, and
            # could collide with one that does.
            _log.warning(
                "skipped source with undecodable filename: %s", _reportable(relative)
            )
            continue
        reason = _excluded(relative, path, excludes=excludes or [])
        if reason is None:
            reason = _non_portable_reason(relative)
        try:
            stat = path.stat()
        except OSError as exc:
            # No metadata at all, so no evidence-backed record can be made --
            # but the skip must still be observable, or this is exactly the
            # silent loss the scope probe above exists to prevent.
            _log.warning(
                "skipped unmeasurable path: %s (%s)", _reportable(relative), exc.strerror
            )
            continue
        if reason is None and stat.st_size > max_file_size:
            reason = "oversized"
        canonical_relative = canonicalize_project_path(relative)
        collided_with = seen_canonical.get(canonical_relative)
        if collided_with is not None:
            # Two distinct Linux files can share one canonical path: NFC/NFD
            # normalization equivalents, or a literal backslash that the
            # canonical form reads as a separator. Identity is deliberately
            # host-independent (AS-ID-001), so the canonical space cannot
            # represent both, and emitting both would abort the whole run at
            # the CODEX-SEC-002 duplicate-identity guard. The first in
            # deterministic order keeps the identity; the collider is
            # reported, never recorded under a synthesized identity the
            # contract does not define.
            _log.warning(
                "skipped canonical-path collision: %s collides with %s (canonical %s)",
                _reportable(relative),
                _reportable(collided_with),
                _reportable(canonical_relative),
            )
            continue
        seen_canonical[canonical_relative] = relative
        if reason == "sensitive-metadata-only":
            digest = None
        else:
            try:
                digest = _sha256(path)
            except OSError:
                # Linux routinely exposes files whose content the caller
                # cannot read (mode 000, foreign ownership under a readable
                # directory). Record the real stat metadata without a digest
                # instead of aborting the entire discovery run.
                digest = None
                reason = reason or "unreadable"
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        project_id, project_uuid = _project_context(path, root)
        source_id = _compatibility_source_id(
            canonical_relative=canonical_relative,
            project_id=project_id,
            root=root,
        )
        source_record = SourceRecord(
            source_id=source_id,
            project_uuid=project_uuid,
            source_lineage_id=None,
            path=relative,
            media_type=_media_type(path),
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
