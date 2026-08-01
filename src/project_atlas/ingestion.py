"""Deterministic text-native ingestion for the Atlas Core vertical slice."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError

from project_atlas.domain.sources import SourceRecord

CLASS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("architecture", ("architecture", "design")),
    ("validation", ("validation", "test report", "acceptance")),
    ("roadmap", ("roadmap", "plan")),
    ("requirements", ("requirement", "specification")),
    ("work-package", ("work package", "work-package", "wp-")),
    ("security", ("security", "threat model")),
    ("project-overview", ("readme", "overview", "project")),
)


def _classify(path: str, text: str) -> tuple[str, str]:
    haystack = f"{path}\n{text[:4000]}".lower()
    for label, signals in CLASS_RULES:
        if any(signal in haystack for signal in signals):
            return label, "deterministic-path-or-heading"
    return "unknown", "no-deterministic-signal"


def _atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


class _PreparedRecord(NamedTuple):
    source: SourceRecord
    source_path: Path
    destination: Path
    text: str


def _inside(root: Path, candidate: Path) -> Path:
    """Resolve a candidate and reject paths escaping ``root``."""
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"destination escapes Vault root: {candidate}") from exc
    return resolved_candidate


def _source_path(root: Path, value: str) -> Path:
    """Resolve a manifest source path without permitting traversal."""
    if not value or Path(value).is_absolute() or "\\" in value:
        raise ValueError(f"unsafe manifest source path: {value!r}")
    parts = Path(value).parts
    if ".." in parts:
        raise ValueError(f"unsafe manifest source path: {value!r}")
    return _inside(root, root / value)


def _manifest_records(manifest: object) -> list[SourceRecord]:
    """Validate the bounded manifest contract at the ingestion boundary."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    required = {"schema_version", "source_root", "sources", "duplicates", "inventory_sha256"}
    allowed = required
    if set(manifest) != allowed:
        raise ValueError("manifest fields do not match schema version 1")
    if manifest["schema_version"] != 1 or not isinstance(manifest["source_root"], str):
        raise ValueError("manifest schema_version or source_root is invalid")
    if not isinstance(manifest["sources"], list) or not isinstance(manifest["duplicates"], dict):
        raise ValueError("manifest sources or duplicates is invalid")
    if not isinstance(manifest["inventory_sha256"], str) or len(manifest["inventory_sha256"]) != 64:
        raise ValueError("manifest inventory_sha256 is invalid")
    records: list[SourceRecord] = []
    for raw in manifest["sources"]:
        if not isinstance(raw, dict):
            raise ValueError("manifest source record must be an object")
        try:
            record = SourceRecord.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"invalid manifest source record: {exc}") from exc
        _source_path(Path(str(manifest["source_root"])).resolve(), record.path)
        records.append(record)
    return records


def ingest(manifest_path: Path, vault: Path) -> dict[str, Any]:
    """Ingest eligible manifest records and create provenance-backed notes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = _manifest_records(manifest)
    root = Path(str(manifest["source_root"])).resolve()
    vault = vault.expanduser().resolve()
    imported: list[dict[str, Any]] = []
    classifications: dict[str, dict[str, str]] = {}
    projects: dict[str, list[dict[str, Any]]] = {}
    prepared: list[_PreparedRecord] = []
    for source_record in sources:
        if source_record.exclusion_reason or not source_record.sha256:
            continue
        source = _source_path(root, source_record.path)
        if not source.is_file():
            raise ValueError(f"manifest source is missing: {source_record.path}")
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise ValueError(f"manifest source is not valid UTF-8: {source_record.path}") from exc
        supported_suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html"}
        suffix = source.suffix.lower() if source.suffix.lower() in supported_suffixes else ".txt"
        destination = _inside(
            vault,
            vault / "sources" / "imported-documents" / f"{source_record.source_id}{suffix}",
        )
        prepared.append(_PreparedRecord(source_record, source, destination, text))
    for source_record, source, destination, text in prepared:
        classification, method = _classify(source_record.path, text)
        source_id = source_record.source_id
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        entry = {
            "source_id": source_id,
            "path": source_record.path,
            "classification": classification,
            "source": f"../../sources/imported-documents/{destination.name}",
            "sha256": source_record.sha256,
        }
        imported.append(entry)
        classifications[source_id] = {"type": classification, "method": method}
        project = source_record.likely_project or "unknown-project"
        projects.setdefault(project, []).append(entry)
    report = {
        "schema_version": 1,
        "inventory_sha256": manifest.get("inventory_sha256"),
        "classifications": classifications,
        "documents_ingested": len(imported),
    }
    _atomic(
        _inside(vault, vault / "sources" / "manifests" / "source-manifest.json"),
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    _atomic(
        _inside(vault, vault / "generated" / "reports" / "ingestion-report.json"),
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    for project, entries in sorted(projects.items()):
        lines = [
            "---", "type: Project", f"title: {project}",
            "knowledge_state: evidence-backed", "---", "", f"# {project}",
            "", "## Sources", "",
        ]
        for entry in sorted(entries, key=lambda item: str(item["path"]).lower()):
            lines.append(
                f"- [{entry['path']}]({entry['source']}) — "
                f"`{entry['classification']}` — `{entry['sha256']}`"
            )
        project_root = _inside(vault, vault / "projects" / project)
        _atomic(_inside(vault, project_root / "project.md"), "\n".join(lines) + "\n")
        map_lines = [
            f"# Documentation map — {project}", "", "| Source | Classification | SHA-256 |",
            "|---|---|---|",
        ]
        for entry in sorted(entries, key=lambda item: str(item["path"]).lower()):
            map_lines.append(
                f"| [{entry['path']}]({entry['source']}) | "
                f"{entry['classification']} | `{entry['sha256']}` |"
            )
        _atomic(
            _inside(vault, project_root / "documentation-map.md"),
            "\n".join(map_lines) + "\n",
        )
    return {
        "ok": True,
        "projects": len(projects),
        "documents_ingested": len(imported),
        "inventory_sha256": manifest.get("inventory_sha256"),
    }
