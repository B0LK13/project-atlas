"""AS-CODER-ALPHA-BRIEF-001 — Unified project intelligence brief.

Assembles derived Coder Alpha answer lenses into one honest briefing for
humans and agents after ``atlas connect``. Does not invent missing fields;
UNKNOWN remains UNKNOWN.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from project_atlas.overview import materialize_overview_lenses
from project_atlas.project_changed import ProjectChangedError, materialize_changed_lenses
from project_atlas.project_decisions import materialize_decisions_lenses
from project_atlas.project_state import materialize_state_lenses
from project_atlas.project_unknown import materialize_unknown_lenses
from project_atlas.web_api.knowledge import list_knowledge_answers

PACKAGE_ID = "AS-CODER-ALPHA-BRIEF-001"
GENERATOR_ID = "atlas-coder-alpha-brief-001"
ANSWERS_RELATIVE = Path("generated") / "answers"
BRIEF_RELATIVE = Path("generated") / "ops" / "project-brief.json"


class ProjectBriefError(ValueError):
    """Fail-closed project brief error."""


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


def _load_answer(vault: Path, answer_id: str) -> dict[str, Any] | None:
    path = vault / ANSWERS_RELATIVE / f"{answer_id}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _field(lens: dict[str, Any] | None, key: str = "summary") -> str | None:
    if not lens:
        return None
    value = lens.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _manifest_source_rows(vault: Path, project_id: str) -> list[dict[str, Any]]:
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    rows = manifest.get("sources") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        return []
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("exclusion_reason"):
            continue
        likely = str(row.get("likely_project") or "unknown-project")
        if likely not in {project_id, "unknown-project"}:
            continue
        selected.append(row)
    return selected


def _stack_from_pyproject(vault: Path, project_id: str) -> str | None:
    """Derive a concrete stack label from root ``pyproject.toml`` when present."""
    for row in _manifest_source_rows(vault, project_id):
        path = str(row.get("path") or "").replace("\\", "/")
        source_id = str(row.get("source_id") or "")
        if path.lower() != "pyproject.toml" or not source_id:
            continue
        imported = vault / "sources" / "imported-documents" / f"{source_id}.md"
        # toml may be stored as imported document text
        if not imported.is_file():
            # some ingests keep original extension via adjacent path; try basename
            alt = vault / "sources" / "imported-documents" / f"{source_id}.toml"
            imported = alt if alt.is_file() else imported
        if not imported.is_file():
            continue
        try:
            text = imported.read_text(encoding="utf-8")
        except OSError:
            continue
        requires = None
        deps: list[str] = []
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("requires-python"):
                requires = stripped.split("=", 1)[-1].strip().strip('"').strip("'")
            if stripped.startswith("dependencies"):
                in_deps = True
                continue
            if in_deps:
                if stripped.startswith("["):
                    in_deps = False
                    continue
                if stripped.startswith("]"):
                    in_deps = False
                    continue
                token = stripped.strip(",").strip('"').strip("'")
                if token and not token.startswith("#"):
                    name = token.split(">=")[0].split("==")[0].split("[")[0].strip()
                    if name:
                        deps.append(name)
        parts: list[str] = []
        if requires:
            parts.append(f"Python {requires}")
        if deps:
            parts.append(", ".join(deps[:6]))
        if parts:
            return " · ".join(parts)[:240]
    return None


def _architecture_rank(path: str) -> tuple[int, int, str] | None:
    """Prefer plan/AGENTS architecture docs over nested READMEs (D-039)."""
    posix = path.replace("\\", "/").lstrip("./")
    lower = posix.lower()
    depth = posix.count("/")
    if lower in {"docs/plan.md", "docs/prp.md"}:
        return (0, depth, posix)
    if lower in {"agents.md", "claude.md"}:
        return (1, depth, posix)
    if lower.endswith("/plan.md") or lower.endswith("/architecture.md"):
        return (2, depth, posix)
    if Path(posix).name.lower() in {"readme.md", "readme.txt", "readme"}:
        return None
    return None


def _architecture_from_text(path: str, text: str, *, max_chars: int = 480) -> str | None:
    """Pull a concrete architecture blurb from plan/AGENTS prose."""
    body = text
    lines = [line.rstrip() for line in body.splitlines()]
    # Prefer an explicit architecture heading when present.
    capture = False
    buf: list[str] = []
    heading_hit = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("#") and any(
            token in lower
            for token in (
                "architect",
                "three-layer",
                "core architectural",
                "package layout",
            )
        ):
            capture = True
            heading_hit = True
            buf = []
            continue
        if capture and stripped.startswith("#"):
            break
        if capture and stripped and not stripped.startswith("```"):
            buf.append(stripped)
            if sum(len(part) for part in buf) >= max_chars:
                break
    if heading_hit and buf:
        text_out = " ".join(buf)
        return text_out[: max_chars - 1].rstrip() + "…" if len(text_out) > max_chars else text_out

    # AGENTS/CLAUDE fallback: three-layer + pipeline signals without inventing.
    signals: list[str] = []
    for line in lines:
        stripped = line.strip().lstrip("-").strip()
        lower = stripped.lower()
        pipeline = "discover" in lower and "ingest" in lower and "validate" in lower
        if "three-layer" in lower or "layer a" in lower or "okf" in lower or pipeline:
            signals.append(stripped)
        if len(signals) >= 3:
            break
    if signals:
        text_out = " ".join(signals)
        return text_out[: max_chars - 1].rstrip() + "…" if len(text_out) > max_chars else text_out
    return None


def _extract_architecture_blurb(vault: Path, project_id: str) -> str | None:
    """Best-effort architecture summary from plan.md / AGENTS.md evidence."""
    candidates: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for row in _manifest_source_rows(vault, project_id):
        path = str(row.get("path") or "")
        rank = _architecture_rank(path)
        if rank is None:
            continue
        candidates.append((rank, row))
    for _rank, row in sorted(candidates, key=lambda item: item[0]):
        source_id = str(row.get("source_id") or "")
        path = str(row.get("path") or "")
        if not source_id:
            continue
        imported = vault / "sources" / "imported-documents" / f"{source_id}.md"
        if not imported.is_file():
            continue
        try:
            text = imported.read_text(encoding="utf-8")
        except OSError:
            continue
        blurb = _architecture_from_text(path, text)
        if blurb:
            return blurb
    return None


def _extract_stack_blurb(vault: Path, project_id: str) -> str | None:
    """Best-effort stack from README ## Stack, else root pyproject.toml."""
    readme_rows: list[tuple[int, dict[str, Any]]] = []
    for row in _manifest_source_rows(vault, project_id):
        path = str(row.get("path") or "").replace("\\", "/")
        if Path(path).name.lower() not in {"readme.md", "readme.txt", "readme"}:
            continue
        depth = path.count("/")
        # Prefer root README over nested package READMEs.
        priority = 0 if depth == 0 else 1 + depth
        if path.startswith(("deps/", "apps/", "integrations/")):
            priority += 10
        readme_rows.append((priority, row))
    for _priority, row in sorted(readme_rows, key=lambda item: item[0]):
        source_id = str(row.get("source_id") or "")
        if not source_id:
            continue
        imported = vault / "sources" / "imported-documents" / f"{source_id}.md"
        if not imported.is_file():
            continue
        try:
            text = imported.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = text.splitlines()
        capture = False
        buf: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("## stack"):
                capture = True
                continue
            if capture and stripped.startswith("#"):
                break
            if capture and stripped:
                buf.append(stripped)
        if buf:
            return " ".join(buf)[:240]
    return _stack_from_pyproject(vault, project_id)


def build_project_brief(
    vault: Path,
    project_id: str,
    *,
    refresh: bool = True,
) -> dict[str, Any]:
    """Build one project brief dict (optionally refreshing lenses first)."""
    if not project_id or project_id in {".", ".."} or "/" in project_id or "\\" in project_id:
        raise ProjectBriefError(f"unsafe project id: {project_id!r}")
    vault = vault.expanduser().resolve()
    if refresh:
        materialize_overview_lenses(vault, project_ids=[project_id])
        materialize_state_lenses(vault, project_ids=[project_id])
        # changed without manifest uses existing inventory pair
        with contextlib.suppress(ProjectChangedError, OSError, ValueError):
            materialize_changed_lenses(vault, project_ids=[project_id])
        materialize_decisions_lenses(vault, project_ids=[project_id])
        materialize_unknown_lenses(vault, project_ids=[project_id])

    overview = _load_answer(vault, f"ans-overview-{project_id}")
    state = _load_answer(vault, f"ans-state-{project_id}")
    changed = _load_answer(vault, f"ans-changed-{project_id}")
    decisions = _load_answer(vault, f"ans-decisions-{project_id}")
    unknown = _load_answer(vault, f"ans-unknown-{project_id}")

    unknown_signals = (unknown or {}).get("signals") if isinstance(unknown, dict) else {}
    coverage_absent = []
    if isinstance(unknown_signals, dict):
        raw_absent = unknown_signals.get("coverage_absent")
        if isinstance(raw_absent, list):
            coverage_absent = [str(item) for item in raw_absent]

    # Suggested next work is honesty-driven, not invented roadmap.
    next_work: list[str] = []
    if isinstance(unknown_signals, dict):
        if int(unknown_signals.get("unresolved_conflicts") or 0) > 0:
            next_work.append("Resolve unresolved conflicts in review/conflicts")
        if int(unknown_signals.get("pending_reviews") or 0) > 0:
            next_work.append("Triage pending human reviews in review/pending")
    if coverage_absent:
        next_work.append(
            "Add source evidence for absent coverage: " + ", ".join(coverage_absent[:6])
        )
    if (decisions or {}).get("status") == "unknown":
        next_work.append("Capture important decisions in docs/DECISIONS.md or ADRs")
    if (changed or {}).get("rollup") == "baseline":
        next_work.append("Re-run atlas connect after edits to populate What Changed")
    if not next_work:
        next_work.append("UNKNOWN - no concrete next-work signal derived from Truth Core")

    evidence = []
    for lens in (overview, state, changed, decisions, unknown):
        if not lens:
            continue
        for item in lens.get("inspected_artifacts") or []:
            if isinstance(item, str) and item not in evidence:
                evidence.append(item)

    tech_stack = _extract_stack_blurb(vault, project_id)
    # D-039: never echo purpose/overview as architecture. Absent evidence → UNKNOWN.
    architecture = _extract_architecture_blurb(vault, project_id)

    brief = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.project-brief.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "project_identity": project_id,
        "purpose": _field(overview) or "UNKNOWN",
        "tech_stack": tech_stack or "UNKNOWN",
        "architecture_summary": architecture or "UNKNOWN",
        "current_state": _field(state) or "UNKNOWN",
        "recent_meaningful_changes": _field(changed) or "UNKNOWN",
        "important_decisions": _field(decisions) or "UNKNOWN",
        "known_problems": _field(unknown) or "UNKNOWN",
        "unknown_or_conflicting": _field(unknown) or "UNKNOWN",
        "suggested_next_work": next_work,
        "evidence_links": evidence[:40],
        "lenses": {
            "overview": (overview or {}).get("answer_id"),
            "state": (state or {}).get("answer_id"),
            "changed": (changed or {}).get("answer_id"),
            "decisions": (decisions or {}).get("answer_id"),
            "unknown": (unknown or {}).get("answer_id"),
        },
        "knowledge_answers": [
            row["answer_id"]
            for row in list_knowledge_answers(vault)
            if row.get("subject") == project_id
        ],
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "release_certified": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
            "fabricated_fields": False,
            "unknown_is_valid": True,
        },
        "notes": [
            "Unified Coder Alpha brief over derived lenses",
            "UI!=canonical",
            "MODEL_OUTPUT!=AUTHORITY",
            "UNKNOWN!=healthy",
        ],
    }
    return brief


def materialize_project_briefs(
    vault: Path,
    *,
    project_ids: list[str] | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Write per-project briefs + aggregate ops receipt."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ProjectBriefError(f"vault is not a directory: {vault}")
    selected = project_ids if project_ids is not None else _list_projects(vault)
    briefs: list[dict[str, Any]] = []
    written: list[str] = []
    for project_id in selected:
        brief = build_project_brief(vault, project_id, refresh=refresh)
        briefs.append(brief)
        path = vault / "generated" / "ops" / f"project-brief-{project_id}.json"
        _write_atomic(
            path,
            (json.dumps(brief, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        written.append(path.relative_to(vault).as_posix())
    receipt = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.brief-receipt.v1",
        "package": PACKAGE_ID,
        "status": "ok",
        "vault": vault.as_posix(),
        "projects": list(selected),
        "briefs_written": written,
        "briefs": briefs,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "release_certified": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
        },
    }
    _write_atomic(
        vault / BRIEF_RELATIVE,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return receipt
