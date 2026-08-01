"""Deterministic text-native ingestion for the Atlas Core vertical slice."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

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


def ingest(manifest_path: Path, vault: Path) -> dict[str, Any]:
    """Ingest eligible manifest records and create provenance-backed notes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(str(manifest["source_root"])).resolve()
    sources = list(manifest.get("sources", []))
    imported: list[dict[str, Any]] = []
    classifications: dict[str, dict[str, str]] = {}
    projects: dict[str, list[dict[str, Any]]] = {}
    for raw in sources:
        if raw.get("exclusion_reason") or not raw.get("sha256"):
            continue
        source = root / str(raw["path"])
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        classification, method = _classify(str(raw["path"]), text)
        source_id = str(raw["source_id"])
        suffix = source.suffix.lower() or ".txt"
        destination = vault / "sources" / "imported-documents" / f"{source_id}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        entry = {
            "source_id": source_id,
            "path": str(raw["path"]),
            "classification": classification,
            "source": f"../../sources/imported-documents/{destination.name}",
            "sha256": raw["sha256"],
        }
        imported.append(entry)
        classifications[source_id] = {"type": classification, "method": method}
        project = str(raw.get("likely_project") or "unknown-project")
        projects.setdefault(project, []).append(entry)
    report = {
        "schema_version": 1,
        "inventory_sha256": manifest.get("inventory_sha256"),
        "classifications": classifications,
        "documents_ingested": len(imported),
    }
    _atomic(
        vault / "sources" / "manifests" / "source-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    _atomic(
        vault / "generated" / "reports" / "ingestion-report.json",
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
        project_root = vault / "projects" / project
        _atomic(project_root / "project.md", "\n".join(lines) + "\n")
        map_lines = [
            f"# Documentation map — {project}", "", "| Source | Classification | SHA-256 |",
            "|---|---|---|",
        ]
        for entry in sorted(entries, key=lambda item: str(item["path"]).lower()):
            map_lines.append(
                f"| [{entry['path']}]({entry['source']}) | "
                f"{entry['classification']} | `{entry['sha256']}` |"
            )
        _atomic(project_root / "documentation-map.md", "\n".join(map_lines) + "\n")
    return {
        "ok": True,
        "projects": len(projects),
        "documents_ingested": len(imported),
        "inventory_sha256": manifest.get("inventory_sha256"),
    }
