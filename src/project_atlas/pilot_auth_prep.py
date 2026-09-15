"""AS-2.1-PILOT-AUTH discovery + prep (expanded bounded search).

Searches registry/config/env/known Atlas workspace roots ONLY.
Never invents markers. Never whole-disk crawls. Fixtures/.tmp/adversarial
are classified and excluded from authentic PASS.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-PILOT-AUTH-001-PREP"
TRUTH_BOUNDARY = (
    "PILOT PREP BOUNDED SEARCH != AUTHENTIC PILOT PASS / != ROOT INVENTION / "
    "!= FIXTURE ESTATE"
)
MARKER = ".atlas-project.yaml"

# Path fragments that prove a marker is fixture/temp — never authentic estate.
_NON_AUTHENTIC_FRAGMENTS: tuple[str, ...] = (
    "/tests/fixtures/",
    "\\tests\\fixtures\\",
    "/fixtures/pilots/",
    "\\fixtures\\pilots\\",
    "/pilot-f407981-clean/",
    "\\pilot-f407981-clean\\",
    "/atlas-vault-documentation/tests/",
    "\\atlas-vault-documentation\\tests\\",
    "/.tmp/",
    "\\.tmp\\",
    "/adversarial/",
    "\\adversarial\\",
    "/corpus-",
    "\\corpus-",
    "/.venv/",
    "\\.venv\\",
    "/site-packages/",
    "\\site-packages\\",
    "/node_modules/",
    "\\node_modules\\",
)


class PilotAuthPrepError(ValueError):
    """Fail-closed pilot prep error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def is_fixture_or_temp_marker(path: Path) -> bool:
    """Return True when a marker path is fixture/temp — not authentic estate."""
    text = str(path)
    lowered = text.lower()
    return any(frag.lower() in lowered for frag in _NON_AUTHENTIC_FRAGMENTS)


def default_known_roots() -> list[Path]:
    """Conservative known-candidate list (registry/local conventions only)."""
    home = Path.home()
    return [
        home / "atlas-estate",
        home / "AtlasEstate",
        home / "projects" / "atlas-estate",
        Path("D:/atlas-estate"),
        Path("D:/AtlasEstate"),
        Path("C:/atlas-estate"),
        Path("D:/project-atlas-vault"),
    ]


def env_configured_roots() -> list[Path]:
    """Roots from operator env registry (AUTHENTIC_ESTATE_ROOT / ATLAS_ESTATE_ROOT)."""
    out: list[Path] = []
    for key in ("AUTHENTIC_ESTATE_ROOT", "ATLAS_ESTATE_ROOT", "ATLAS_PILOT_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            out.append(Path(raw))
    return out


def known_atlas_workspace_roots() -> list[Path]:
    """Known Atlas workspace containers (bounded; not whole-disk)."""
    return [
        Path("D:/atlas-worktrees"),
        Path("D:/project-atlas-orphans"),
        Path("D:/project-atlas-vault"),
    ]


def _collect_markers_under(root: Path, *, max_depth: int = 4) -> list[Path]:
    """Collect marker files under root with a hard depth cap."""
    if not root.is_dir():
        return []
    found: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).resolve().relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if depth > max_depth:
            dirnames[:] = []
            continue
        # Prune heavy/irrelevant trees early.
        dirnames[:] = [
            d
            for d in dirnames
            if d
            not in {
                ".git",
                ".venv",
                "node_modules",
                "__pycache__",
                ".mypy_cache",
                ".ruff_cache",
                ".pytest_cache",
            }
        ]
        if MARKER in filenames:
            found.append(Path(dirpath) / MARKER)
    return found


def expand_candidate_roots(
    extra: Iterable[Path] | None = None,
) -> list[Path]:
    """Union of env + known conventions + explicit extras (deduped)."""
    ordered: list[Path] = []
    seen: set[str] = set()
    for item in [
        *env_configured_roots(),
        *default_known_roots(),
        *(list(extra) if extra is not None else []),
    ]:
        key = str(Path(item))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(Path(item))
    return ordered


def scan_known_pilot_roots(
    candidates: Iterable[Path] | None = None,
    *,
    operator: OperatorProfile | None = None,
    include_workspace_scan: bool | None = None,
) -> dict[str, Any]:
    """Scan bounded candidates for authentic markers; never create them.

    When ``candidates`` is explicitly provided (unit tests / narrow scan),
    workspace walk defaults off. Full CLI prep (candidates=None) enables
    env+known roots and bounded workspace scan.
    """
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("pilot.scan")

    authentic: list[dict[str, str]] = []
    fixtures: list[dict[str, str]] = []
    missing: list[str] = []
    checked: list[str] = []

    do_workspace = (
        include_workspace_scan
        if include_workspace_scan is not None
        else candidates is None
    )

    roots = (
        list(candidates)
        if candidates is not None
        else expand_candidate_roots()
    )

    def _consider_marker(marker: Path, *, source: str) -> None:
        if not marker.is_file():
            return
        row = {
            "root": str(marker.parent.resolve()),
            "marker": str(marker.resolve()),
            "source": source,
        }
        if is_fixture_or_temp_marker(marker):
            row["status"] = "FIXTURE_OR_TEMP"
            fixtures.append(row)
        else:
            row["status"] = "FOUND_AUTHENTIC"
            authentic.append(row)

    for raw in roots:
        root = Path(raw)
        checked.append(str(root))
        marker = root / MARKER
        if marker.is_file():
            _consider_marker(marker, source="direct-candidate")
        else:
            missing.append(str(root))

    if do_workspace:
        for ws in known_atlas_workspace_roots():
            checked.append(f"workspace-scan:{ws}")
            if not ws.exists():
                missing.append(str(ws))
                continue
            for marker in _collect_markers_under(ws, max_depth=5):
                _consider_marker(marker, source="workspace-bounded-scan")

    # Prefer env-configured authentic roots first, then lexical.
    def _rank(row: dict[str, str]) -> tuple[int, str]:
        src = row.get("source", "")
        pri = 0 if src == "direct-candidate" else 1
        return (pri, row["root"])

    authentic_sorted = sorted(authentic, key=_rank)
    selected = authentic_sorted[0] if authentic_sorted else None

    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "authentic_found": len(authentic_sorted),
        "fixture_or_temp_found": len(fixtures),
        "found": authentic_sorted,
        "fixture_or_temp_sample": fixtures[:20],
        "missing_count": len(missing),
        "missing_sample": missing[:30],
        "checked_sample": checked[:40],
        "selected_authentic_root": selected["root"] if selected else None,
        "authentic_estate_pilot": False,
        "pilot_pass": False,
        "escalation_required": len(authentic_sorted) == 0,
        "owner_blocked": len(authentic_sorted) == 0,
        "wake_event": (
            None
            if authentic_sorted
            else "AUTHENTIC_ESTATE_ROOT_AVAILABLE"
        ),
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }


def write_pilot_prep_report(
    vault: Path,
    *,
    report_id: str = "pilot-prep",
    candidates: Iterable[Path] | None = None,
    operator: OperatorProfile | None = None,
    include_workspace_scan: bool | None = None,
) -> dict[str, Any]:
    """Persist a prep report under generated/ops/pilot/."""
    payload = scan_known_pilot_roots(
        candidates,
        operator=operator,
        include_workspace_scan=include_workspace_scan,
    )
    payload["report_id"] = report_id
    out = vault / "generated" / "ops" / "pilot" / f"{report_id}-prep.json"
    _atomic_write_json(out, payload)
    return payload
