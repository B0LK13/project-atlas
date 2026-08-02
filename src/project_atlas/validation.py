"""Strict structural and provenance validation for the Core slice."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from project_atlas.domain.source_registry import SourceLineageRecord
from project_atlas.schema import validate_record

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
    registry = vault / "state" / "sources.json"
    if registry.is_file():
        try:
            raw = json.loads(registry.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 2:
                raise ValueError("source registry schema_version must be 2")
            values = raw.get("sources")
            if not isinstance(values, list):
                raise ValueError("source registry sources must be a list")
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError("source registry records must be objects")
                validated = SourceLineageRecord.model_validate(value)
                validate_record(validated, "source-registry")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            errors.append(f"invalid source registry: {exc}")
    return {"ok": not errors, "errors": errors, "markdown_files": len(list(vault.rglob("*.md")))}
