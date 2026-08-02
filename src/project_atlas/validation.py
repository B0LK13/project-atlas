"""Strict structural and provenance validation for the Core slice."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.schema import SchemaValidationError, validate_record

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
    _validate_knowledge_state(vault, errors)
    return {"ok": not errors, "errors": errors, "markdown_files": len(list(vault.rglob("*.md")))}


def _validate_knowledge_state(vault: Path, errors: list[str]) -> None:
    """Validate AS-CORE-003 machine state and provenance confinement."""
    sources: dict[str, str | None] = {}
    sources_by_lineage: dict[str, str | None] = {}
    source_state = vault / "state" / "sources.json"
    if source_state.is_file():
        try:
            raw = json.loads(source_state.read_text(encoding="utf-8"))
            source_items = [item for item in raw.get("sources", []) if isinstance(item, dict)]
            for item in source_items:
                if item.get("source_lineage_id"):
                    sources_by_lineage[str(item["source_lineage_id"])] = item.get(
                        "current_content_sha256", item.get("sha256")
                    )
                if item.get("source_id"):
                    source_id = str(item["source_id"])
                    if source_id in sources and sources[source_id] != item.get("sha256"):
                        sources[source_id] = None
                    else:
                        sources[source_id] = item.get("sha256")
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            errors.append(f"invalid source state for knowledge validation: {exc}")
    for path in _json_files(vault, "state", "claims"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for claim in raw.get("claims", []):
                validate_record(claim, "claim")
                for ref in claim.get("provenance", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid claim state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "concepts"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for concept in raw.get("concepts", []):
                validate_record(concept, "concept-record")
                for ref in concept.get("sources", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid concept state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "review", "conflicts"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for conflict in raw.get("entries", []):
                validate_record(conflict, "conflict-record")
                for ref in conflict.get("provenance", []):
                    _validate_provenance(vault, ref, sources, sources_by_lineage, errors, path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid conflict state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "review", "pending"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for review in raw.get("entries", []):
                validate_record(review, "review-entry")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid review state {path.relative_to(vault)}: {exc}")
    for path in _json_files(vault, "state", "claim-lifecycle"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for lifecycle in raw.get("claims", []):
                validate_record(lifecycle, "claim-lifecycle")
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            SchemaValidationError,
            AttributeError,
            TypeError,
        ) as exc:
            errors.append(f"invalid lifecycle state {path.relative_to(vault)}: {exc}")


def _json_files(vault: Path, *parts: str) -> list[Path]:
    directory = vault.joinpath(*parts)
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def _validate_provenance(
    vault: Path,
    reference: dict[str, Any],
    sources: dict[str, str | None],
    sources_by_lineage: dict[str, str | None],
    errors: list[str],
    owner: Path,
) -> None:
    resource = str(reference.get("resource", ""))
    candidate = (vault / resource).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError:
        errors.append(f"provenance escapes Vault: {owner.relative_to(vault)} -> {resource}")
        return
    if not candidate.is_file():
        errors.append(f"provenance target missing: {owner.relative_to(vault)} -> {resource}")
        return
    source_id = str(reference.get("source_id", ""))
    source_lineage_id = reference.get("source_lineage_id")
    expected = (
        sources_by_lineage.get(str(source_lineage_id))
        if source_lineage_id
        else sources.get(source_id)
    )
    actual = _sha256(candidate)
    if expected and actual != expected:
        errors.append(f"provenance hash mismatch: {owner.relative_to(vault)} -> {source_id}")
    supplied = reference.get("sha256")
    # Agent-event provenance uses the package aggregate hash, while the
    # resource is the human-readable event projection. Package integrity is
    # verified at ingestion; it is not the byte hash of this projection.
    if supplied and not reference.get("receipt_id") and actual != supplied:
        errors.append(f"claim hash mismatch: {owner.relative_to(vault)} -> {source_id}")


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
