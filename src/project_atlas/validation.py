"""Strict structural and provenance validation for the Core slice."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

LINK = re.compile(r"\]\(([^)]+)\)")


def validate(vault: Path) -> dict[str, Any]:
    errors: list[str] = []
    for required in ("index.md", "projects/index.md", "sources/index.md", "01-portfolio/index.md"):
        if not (vault / required).is_file():
            errors.append(f"missing required generated file: {required}")
    for markdown in sorted(vault.rglob("*.md")):
        if ".tmp" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            candidate = (markdown.parent / target.split("#", 1)[0]).resolve()
            try:
                candidate.relative_to(vault.resolve())
            except ValueError:
                errors.append(f"link escapes vault: {markdown.relative_to(vault)} -> {target}")
            else:
                if not candidate.is_file():
                    errors.append(f"broken link: {markdown.relative_to(vault)} -> {target}")
    return {"ok": not errors, "errors": errors, "markdown_files": len(list(vault.rglob("*.md")))}
