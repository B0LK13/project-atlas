"""Bounded project discovery for AS-WP-004."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from internal import project_markers

SAFE_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    root: str
    identity_source: str
    markers: tuple[str, ...] = ()
    manifest_path: str | None = None
    aliases: tuple[str, ...] = ()
    status: str = "unknown"
    project_type: str = "unknown"
    warnings: tuple[str, ...] = ()
    discovery: dict[str, Any] = field(default_factory=dict, compare=False)
    authority: dict[str, Any] = field(default_factory=dict, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not SAFE_PROJECT_ID.fullmatch(result):
        raise ValueError(f"unsafe or empty project id derived from {value!r}")
    return result


def _manifest(path: Path) -> dict[str, Any]:
    manifest = path / ".atlas-project.yaml"
    if not manifest.is_file():
        return {}
    try:
        import yaml
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid project manifest {manifest}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("project"), dict):
        raise ValueError(f"invalid project manifest {manifest}: project mapping required")
    return data


def _record(root: Path) -> ProjectRecord:
    data = _manifest(root)
    project = data.get("project", {})
    manifest = root / ".atlas-project.yaml"
    project_id = str(project.get("id") or _slug(root.name))
    if not SAFE_PROJECT_ID.fullmatch(project_id):
        raise ValueError(f"unsafe project id: {project_id!r}")
    markers = tuple(marker for marker in project_markers.DEFAULT_MARKERS if (root / marker).exists())
    discovery = data.get("discovery", {}) if isinstance(data.get("discovery", {}), dict) else {}
    authority = data.get("authority", {}) if isinstance(data.get("authority", {}), dict) else {}
    aliases = project.get("aliases", []) if isinstance(project.get("aliases", []), list) else []
    return ProjectRecord(
        project_id=project_id,
        name=str(project.get("name") or root.name),
        root=str(root.resolve()),
        identity_source="atlas-project-manifest" if manifest.is_file() else "root-derived",
        markers=markers,
        manifest_path=manifest.as_posix() if manifest.is_file() else None,
        aliases=tuple(str(alias) for alias in aliases),
        status=str(project.get("status", "unknown")),
        project_type=str(project.get("type", "unknown")),
        discovery=discovery,
        authority=authority,
    )


def discover_projects(
    workspace_root: Path,
    *,
    project_root: Path | None = None,
    max_depth: int = 4,
    nested_repository_policy: str = "parent-project",
) -> list[ProjectRecord]:
    """Discover bounded projects without following directory symlinks."""
    root = workspace_root.expanduser().resolve()
    if project_root is not None:
        candidate = project_root.expanduser().resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("project root is outside workspace root") from exc
        return [_record(candidate)]
    found: list[ProjectRecord] = []
    for current, dirs, _files in __import__("os").walk(root, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        for name in list(dirs):
            candidate = current_path / name
            if candidate.is_symlink():
                try:
                    candidate.resolve().relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"symlink escapes workspace: {candidate}") from exc
        dirs[:] = [name for name in dirs if not project_markers.is_excluded_dir(name)]
        if depth > max_depth:
            dirs[:] = []
            continue
        if project_markers.has_marker(current_path):
            found.append(_record(current_path))
            if nested_repository_policy == "parent-project":
                dirs[:] = []
    unique: dict[str, ProjectRecord] = {}
    for record in found:
        previous = unique.get(record.project_id)
        if previous is not None and previous.root != record.root:
            raise ValueError(f"duplicate project id {record.project_id!r}: {previous.root} and {record.root}")
        unique[record.project_id] = record
    return [unique[key] for key in sorted(unique)]


def serialize_records(records: list[ProjectRecord]) -> str:
    return json.dumps([record.as_dict() for record in records], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
