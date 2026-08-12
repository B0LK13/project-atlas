"""AS-CODER-ALPHA-UNKNOWN-001 — Unknown/conflict/review honesty lens.

Bundles unresolved conflicts, pending reviews, absent coverage, and other
UNKNOWN signals into ``generated/answers/ans-unknown-<project>.json``.

Honesty: UNKNOWN is a valid result; rollup != trust score; lens != authority.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

PACKAGE_ID = "AS-CODER-ALPHA-UNKNOWN-001"
GENERATOR_ID = "atlas-coder-alpha-unknown-001"
ANSWERS_RELATIVE = Path("generated") / "answers"
_JSON_FENCE_RE = re.compile(
    r"## Semantic record\s*```json\s*(.*?)\s*```",
    re.DOTALL | re.IGNORECASE,
)
_STATUS_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([0-9]+)\s*\|\s*$",
    re.MULTILINE,
)


class ProjectUnknownError(ValueError):
    """Fail-closed unknown/conflict lens error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _list_projects(vault: Path) -> list[str]:
    root = vault / "projects"
    if not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def _safe_project_id(project_id: str) -> str:
    if not project_id or project_id in {".", ".."} or "/" in project_id or "\\" in project_id:
        raise ProjectUnknownError(f"unsafe project id: {project_id!r}")
    return project_id


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _entry_count(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 0
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return 0
    # HUMAN-LOOP-001: decided reviews (resolved/rejected) are not pending UNKNOWN.
    pending = [
        entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("status") or "pending") == "pending"
    ]
    return len(pending)


def _parse_status_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _STATUS_ROW_RE.finditer(text):
        label = match.group(1).strip().lower()
        if label in {"signal"} or set(label) <= {"-"}:
            continue
        counts[label] = int(match.group(2))
    return counts


def _coverage_absent(project_md: str) -> list[str]:
    match = _JSON_FENCE_RE.search(project_md)
    if not match:
        return []
    try:
        semantic = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    if not isinstance(semantic, dict):
        return []
    coverage = semantic.get("coverage")
    if not isinstance(coverage, list):
        return []
    absent: list[str] = []
    for row in coverage:
        if isinstance(row, dict) and row.get("state") == "absent":
            category = row.get("category")
            if isinstance(category, str):
                absent.append(category)
    return sorted(absent)


def build_unknown_lens(vault: Path, project_id: str) -> dict[str, Any]:
    """Build one derived unknown/conflict lens for ``project_id``."""
    project_id = _safe_project_id(project_id)
    inspected: list[str] = []
    pending_path = vault / "review" / "pending" / f"{project_id}.json"
    conflicts_path = vault / "review" / "conflicts" / f"{project_id}.json"
    status_path = vault / "projects" / project_id / "knowledge-status.md"
    project_note = vault / "projects" / project_id / "project.md"

    pending = _read_json(pending_path)
    conflicts = _read_json(conflicts_path)
    if pending_path.is_file():
        inspected.append(pending_path.relative_to(vault).as_posix())
    if conflicts_path.is_file():
        inspected.append(conflicts_path.relative_to(vault).as_posix())

    status_counts: dict[str, int] = {}
    if status_path.is_file():
        inspected.append(status_path.relative_to(vault).as_posix())
        try:
            status_counts = _parse_status_counts(status_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ProjectUnknownError(f"unreadable knowledge-status: {exc}") from exc

    absent_coverage: list[str] = []
    lifecycle = "unknown"
    if project_note.is_file():
        inspected.append(project_note.relative_to(vault).as_posix())
        try:
            note_text = project_note.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectUnknownError(f"unreadable project note: {exc}") from exc
        absent_coverage = _coverage_absent(note_text)
        match = _JSON_FENCE_RE.search(note_text)
        if match:
            try:
                semantic = json.loads(match.group(1))
            except json.JSONDecodeError:
                semantic = None
            if isinstance(semantic, dict) and isinstance(semantic.get("lifecycle"), str):
                lifecycle = semantic["lifecycle"] or "unknown"

    # HUMAN-LOOP-001: pending queue is authoritative for human-decided reviews.
    # Do not let stale knowledge-status.md "claims awaiting review" resurrect
    # counts after atlas review decide (status report refreshes only on compile).
    if pending is not None:
        pending_count = _entry_count(pending)
    else:
        pending_count = status_counts.get("claims awaiting review", 0)
    conflict_count = max(
        _entry_count(conflicts),
        status_counts.get("unresolved conflicts", 0),
    )
    stale = status_counts.get("stale claims", 0)
    withheld = status_counts.get("claims withheld", 0)
    sources_failed = status_counts.get("sources failed", 0)

    unknowns: list[str] = []
    if conflict_count:
        unknowns.append(f"unresolved_conflicts={conflict_count}")
    if pending_count:
        unknowns.append(f"pending_reviews={pending_count}")
    if stale:
        unknowns.append(f"stale_claims={stale}")
    if withheld:
        unknowns.append(f"claims_withheld={withheld}")
    if sources_failed:
        unknowns.append(f"sources_failed={sources_failed}")
    if lifecycle in {"", "unknown"}:
        unknowns.append("lifecycle=unknown")
    if absent_coverage:
        unknowns.append("coverage_absent=" + ",".join(absent_coverage[:8]))

    if conflict_count or sources_failed:
        rollup = "conflict"
    elif pending_count or stale or withheld:
        rollup = "review"
    elif unknowns:
        rollup = "unknown"
    else:
        rollup = "clear"

    if unknowns:
        status = "derived"
        summary = f"rollup={rollup}; " + "; ".join(unknowns)
        value = summary
    else:
        status = "derived"
        summary = "rollup=clear; no pending reviews, conflicts, or UNKNOWN signals"
        value = summary

    notes = [
        "Bundled honesty surface over conflicts/reviews/coverage/lifecycle",
        "lens!=Layer-B-authority",
        "UI!=canonical",
        "UNKNOWN!=healthy",
        "rollup!=trust-score",
    ]

    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.unknown-lens.v1",
        "package": PACKAGE_ID,
        "answer_id": f"ans-unknown-{project_id}",
        "subject": project_id,
        "field": "unknown_conflicts",
        "title": "What is unknown or conflicting?",
        "summary": summary,
        "value": value,
        "status": status,
        "authority": "derived-lens",
        "layer": "C",
        "project_id": project_id,
        "rollup": rollup,
        "signals": {
            "pending_reviews": pending_count,
            "unresolved_conflicts": conflict_count,
            "stale_claims": stale,
            "claims_withheld": withheld,
            "sources_failed": sources_failed,
            "lifecycle": lifecycle,
            "coverage_absent": absent_coverage,
            "unknown_items": unknowns,
        },
        "inspected_artifacts": inspected,
        "notes": notes,
        "generated": {"by": GENERATOR_ID},
    }


def materialize_unknown_lenses(
    vault: Path,
    *,
    project_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Write unknown/conflict answer lenses under ``generated/answers/``."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ProjectUnknownError(f"vault is not a directory: {vault}")
    selected = project_ids if project_ids is not None else _list_projects(vault)
    written: list[str] = []
    lenses: list[dict[str, Any]] = []
    for project_id in selected:
        lens = build_unknown_lens(vault, project_id)
        lenses.append(lens)
        path = vault / ANSWERS_RELATIVE / f"{lens['answer_id']}.json"
        _write_atomic(
            path,
            (json.dumps(lens, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        written.append(path.relative_to(vault).as_posix())
    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.unknown-receipt.v1",
        "package": PACKAGE_ID,
        "status": "ok",
        "vault": vault.as_posix(),
        "projects": list(selected),
        "answers_written": written,
        "lenses": lenses,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "release_certified": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
        },
    }
