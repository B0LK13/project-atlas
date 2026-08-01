"""Deterministic index generation for compiled Atlas Core output."""

from __future__ import annotations

import os
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def build_indexes(vault: Path) -> dict[str, int | bool]:
    """Build project, portfolio and source indexes from existing Markdown."""
    projects_root = vault / "projects"
    projects = (
        sorted(path for path in projects_root.iterdir() if path.is_dir())
        if projects_root.is_dir()
        else []
    )
    project_lines = ["# Projects", ""]
    for project in projects:
        project_lines.append(f"- [{project.name}]({project.name}/project.md)")
    _write(vault / "projects" / "index.md", "\n".join(project_lines) + "\n")
    portfolio_lines = ["# Portfolio", "", "Generated from canonical project projections.", ""]
    for project in projects:
        portfolio_lines.append(f"- [{project.name}](../projects/{project.name}/project.md)")
    _write(vault / "01-portfolio" / "index.md", "\n".join(portfolio_lines) + "\n")
    source_root = vault / "sources" / "imported-documents"
    source_files = sorted(source_root.glob("*")) if source_root.is_dir() else []
    source_lines = ["# Sources", ""] + [
        f"- [{path.name}](imported-documents/{path.name})" for path in source_files
    ]
    _write(vault / "sources" / "index.md", "\n".join(source_lines) + "\n")
    return {"ok": True, "projects": len(projects), "sources": len(source_files)}
