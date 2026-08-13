"""AS-CODER-ALPHA-DECISIONS-001 — Decision memory derived lens from Core.

Surfaces important decisions from:
- Layer B ``projects/<id>/decisions.md`` headings (when present)
- Layer A imported decision/ADR docs (heading harvest)
- persisted claims with ``claim_type == decision``

Honesty: lens != authority; UNKNOWN when no decision evidence exists.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

PACKAGE_ID = "AS-CODER-ALPHA-DECISIONS-001"
GENERATOR_ID = "atlas-coder-alpha-decisions-001"
ANSWERS_RELATIVE = Path("generated") / "answers"
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_DECISION_PATH_HINTS = ("decision", "adr", "rfc")
_NON_DECISION_HINTS = (
    "implementation note",
    "changelog",
    "release notes",
    "todo",
    "scratch",
    "release certified",
    "accepted = yes",
    "receipt.md",
    "signed receipt",
)


def _classify_decision_status(
    title: str,
    *,
    kind: str,
    path: str = "",
    lifecycle: str | None = None,
    verification: str | None = None,
) -> str:
    """Deterministic decision status label (no confidence score).

    Structured claim lifecycle/verification wins over title heuristics when
    present (AGENTS.md: objective signals, not prose theatre).
    """
    life = (lifecycle or "").strip().lower()
    ver = (verification or "").strip().lower()
    if life in {"superseded", "stale", "stale-or-superseded"}:
        return "SUPERSEDED"
    if life in {"rejected"} or ver in {"rejected"}:
        return "REJECTED"
    if life in {"contradicted"}:
        return "OPEN_PROPOSED"
    if ver in {"pending", "conflicting"}:
        return "OPEN_PROPOSED"

    lower = title.strip().lower()
    path_l = path.lower()
    if any(hint in lower for hint in _NON_DECISION_HINTS):
        return "NON_DECISION"
    if "superseded" in lower or "obsolete" in lower:
        return "SUPERSEDED"
    if "rejected" in lower or "declined" in lower:
        return "REJECTED"
    if "proposed" in lower or "open question" in lower or "wip" in lower:
        return "OPEN_PROPOSED"
    if "historical" in lower or "archive" in path_l:
        return "HISTORICAL"
    # Certification / receipt theatre is not a governing product decision.
    if any(
        token in path_l
        for token in ("/receipt", "receipt.md", "/demo/", "fixtures/")
    ):
        return "NON_DECISION" if kind == "imported-heading" else "HISTORICAL"
    if kind == "claim" or "adr" in path_l or kind == "project-note":
        return "ACTIVE_GOVERNING"
    if kind == "imported-heading":
        return "HISTORICAL" if "receipt" in path_l else "OPEN_PROPOSED"
    return "IMPLEMENTATION_NOTE"


class ProjectDecisionsError(ValueError):
    """Fail-closed decisions lens error."""


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
        raise ProjectDecisionsError(f"unsafe project id: {project_id!r}")
    return project_id


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _headings(text: str) -> list[str]:
    titles: list[str] = []
    for match in _HEADING_RE.finditer(text):
        title = match.group(2).strip()
        if not title:
            continue
        # Skip boilerplate titles.
        lowered = title.lower()
        if lowered.startswith("decisions"):
            continue
        if lowered in {"stack", "architecture", "overview", "readme"}:
            continue
        titles.append(title)
    return titles


def _decision_headings_from_note(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if "_No verified agent events" in text and text.count("#") <= 1:
        return []
    return _headings(text)


def _manifest_sources(vault: Path) -> list[dict[str, Any]]:
    payload = _read_json(vault / "generated" / "ops" / "connect-manifest.json")
    if not payload:
        return []
    rows = payload.get("sources")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and not row.get("exclusion_reason")]


def _decision_headings_from_imports(vault: Path, project_id: str) -> list[dict[str, str]]:
    """Harvest decision-like headings from imported Layer A docs."""
    rows = _manifest_sources(vault)
    found: list[dict[str, str]] = []
    for row in rows:
        likely = str(row.get("likely_project") or "unknown-project")
        if likely not in {project_id, "unknown-project"}:
            continue
        path = str(row.get("path") or "")
        source_id = str(row.get("source_id") or "")
        path_l = path.lower()
        if not any(hint in path_l for hint in _DECISION_PATH_HINTS):
            continue
        if not source_id:
            continue
        imported = vault / "sources" / "imported-documents" / f"{source_id}.md"
        if not imported.is_file():
            continue
        try:
            text = imported.read_text(encoding="utf-8")
        except OSError:
            continue
        for title in _headings(text)[:8]:
            status = _classify_decision_status(title, kind="imported-heading", path=path)
            if status == "NON_DECISION":
                continue
            found.append(
                {
                    "title": title,
                    "source": imported.relative_to(vault).as_posix(),
                    "kind": "imported-heading",
                    "path": path,
                    "status": status,
                    "authority": "imported-heading",
                }
            )
    return found[:20]


def _decision_claims(vault: Path, project_id: str) -> list[dict[str, str]]:
    payload = _read_json(vault / "state" / "claims" / f"{project_id}.json")
    if not payload:
        return []
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return []
    out: list[dict[str, str]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_type = str(claim.get("claim_type") or "")
        if claim_type != "decision" and "decision" not in claim_type:
            continue
        title = str(claim.get("value") or claim.get("normalized_text") or claim.get("field") or "")
        if not title.strip():
            continue
        status = _classify_decision_status(
            title,
            kind="claim",
            lifecycle=str(claim.get("lifecycle") or "") or None,
            verification=str(claim.get("verification") or "") or None,
        )
        out.append(
            {
                "title": title.strip()[:200],
                "claim_id": str(claim.get("claim_id") or ""),
                "kind": "claim",
                "status": status,
                "authority": "claim",
                "lifecycle": str(claim.get("lifecycle") or ""),
            }
        )
    return out[:20]


def build_decisions_lens(vault: Path, project_id: str) -> dict[str, Any]:
    """Build one derived decisions lens for ``project_id``."""
    project_id = _safe_project_id(project_id)
    inspected: list[str] = []
    decisions: list[dict[str, str]] = []

    note = vault / "projects" / project_id / "decisions.md"
    if note.is_file():
        inspected.append(note.relative_to(vault).as_posix())
        for title in _decision_headings_from_note(note):
            status = _classify_decision_status(title, kind="project-note")
            if status == "NON_DECISION":
                continue
            decisions.append(
                {
                    "title": title,
                    "source": note.relative_to(vault).as_posix(),
                    "kind": "project-note",
                    "status": status,
                    "authority": "project-note",
                }
            )

    claims_path = vault / "state" / "claims" / f"{project_id}.json"
    if claims_path.is_file():
        inspected.append(claims_path.relative_to(vault).as_posix())
    decisions.extend(_decision_claims(vault, project_id))

    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    if manifest_path.is_file():
        inspected.append(manifest_path.relative_to(vault).as_posix())
    decisions.extend(_decision_headings_from_imports(vault, project_id))

    # Deduplicate by normalized title.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in decisions:
        key = item["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if unique:
        status = "derived"
        active = [item for item in unique if item.get("status") == "ACTIVE_GOVERNING"]
        focus = active or [
            item
            for item in unique
            if item.get("status") not in {"NON_DECISION", "HISTORICAL", "SUPERSEDED"}
        ]
        focus = focus or unique
        titles = [
            f"{item['title']} [{item.get('status', 'UNKNOWN')}]" for item in focus[:8]
        ]
        summary = (
            f"decisions={len(unique)}; active_governing={len(active)}; "
            + "; ".join(titles)
        )
        if len(summary) > 480:
            summary = summary[:479].rstrip() + "…"
        value = summary
        notes = [
            "Derived from decisions note + decision claims + ADR/decision source headings",
            "status labels are deterministic classifiers, not confidence scores",
            "lens!=Layer-B-authority",
            "UI!=canonical",
            "not a ranked trust score",
        ]
    else:
        status = "unknown"
        summary = None
        value = None
        notes = [
            "No decision evidence found in note/claims/ADR sources; UNKNOWN",
            "lens!=Layer-B-authority",
            "UI!=canonical",
            "UNKNOWN!=healthy",
        ]

    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.decisions-lens.v1",
        "package": PACKAGE_ID,
        "answer_id": f"ans-decisions-{project_id}",
        "subject": project_id,
        "field": "decisions",
        "title": "What decisions matter?",
        "summary": summary,
        "value": value,
        "status": status,
        "authority": "derived-lens",
        "layer": "C",
        "project_id": project_id,
        "decisions": unique[:20],
        "decision_count": len(unique),
        "inspected_artifacts": inspected,
        "notes": notes,
        "generated": {"by": GENERATOR_ID},
    }


def materialize_decisions_lenses(
    vault: Path,
    *,
    project_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Write decisions answer lenses under ``generated/answers/``."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ProjectDecisionsError(f"vault is not a directory: {vault}")
    selected = project_ids if project_ids is not None else _list_projects(vault)
    written: list[str] = []
    lenses: list[dict[str, Any]] = []
    for project_id in selected:
        lens = build_decisions_lens(vault, project_id)
        lenses.append(lens)
        path = vault / ANSWERS_RELATIVE / f"{lens['answer_id']}.json"
        _write_atomic(
            path,
            (json.dumps(lens, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        written.append(path.relative_to(vault).as_posix())
    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.decisions-receipt.v1",
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
