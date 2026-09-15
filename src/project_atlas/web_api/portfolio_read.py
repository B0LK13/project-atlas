"""AS-CODER-ALPHA-PORTFOLIO-READ-001 -- vault-scoped portfolio REPORT READ.

Read-only consume of persisted AS-MVP-001 Layer C artifacts under
``generated/portfolio/*.json``. This module never invokes
``build_portfolio`` / ``build_portfolio_payloads`` / ``_promote``, never
writes, and never treats Layer C as Truth Core or authority.

Honesty:
- PORTFOLIO != AUTHORITY
- LAYER C != TRUTH CORE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- Not intelligence ``read_portfolio_state`` rematerialize
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-PORTFOLIO-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-portfolio-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.portfolio-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-MVP-001",)
SOURCE_RELATIVE_DIR: Final[str] = "generated/portfolio"
SOURCE_COMMAND: Final[str] = "atlas portfolio-status"
EXPECTED_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "capability-report.json",
        "dependency-report.json",
        "documentation-coverage.json",
        "maturity-matrix.json",
        "overview.json",
        "stale-knowledge.json",
    }
)
TRUTH_BOUNDARY: Final[str] = (
    "PORTFOLIO != AUTHORITY / LAYER C != TRUTH CORE / EMPTY != HEALTHY / "
    "UNKNOWN != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "NOT INTEL PORTFOLIO-STATE REMATERIALIZE / "
    "src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "PORTFOLIO != AUTHORITY",
    "LAYER C != TRUTH CORE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "NOT INTEL PORTFOLIO-STATE REMATERIALIZE",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebPortfolioReadError(ValueError):
    """Fail-closed portfolio REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "portfolio_is_authority": False,
        "layer_c_is_truth_core": False,
        "auto_execution": False,
        "materialize_invoked": False,
        "derive_invoked": False,
        "build_portfolio_invoked": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "not_intel_portfolio_state": True,
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebPortfolioReadError(f"portfolio-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebPortfolioReadError("portfolio-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebPortfolioReadError("portfolio-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebPortfolioReadError("portfolio-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebPortfolioReadError("portfolio-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebPortfolioReadError(f"portfolio-read-merge-authority-invented:{name}")
    if (
        payload.get("portfolio_is_authority") is True
        or payload.get("lens_is_authority") is True
        or payload.get("layer_c_is_truth_core") is True
    ):
        raise WebPortfolioReadError("portfolio-read-authority-invented")


def _safe_filename(name: str) -> bool:
    if not name.endswith(".json") or not name or name.startswith("."):
        return False
    return not ("/" in name or "\\" in name or ".." in name)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebPortfolioReadError(f"portfolio-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebPortfolioReadError(f"portfolio-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _existing_portfolio_artifacts(vault: Path) -> dict[str, Any]:
    portfolio_dir = vault / SOURCE_RELATIVE_DIR
    rows: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    malformed = 0
    if portfolio_dir.exists():
        if portfolio_dir.is_symlink():
            raise WebPortfolioReadError("portfolio-read-symlink-forbidden")
        if not portfolio_dir.is_dir():
            raise WebPortfolioReadError("portfolio-read-portfolio-not-directory")
        _inside(vault, portfolio_dir)
        for child in sorted(portfolio_dir.iterdir(), key=lambda path: path.name):
            name = child.name
            if not _safe_filename(name):
                if name.endswith(".json"):
                    skipped_names.append(name)
                continue
            if child.is_symlink():
                raise WebPortfolioReadError("portfolio-read-symlink-forbidden")
            if not child.is_file():
                raise WebPortfolioReadError(f"portfolio-read-artifact-not-file:{name}")
            resolved = _inside(vault, child)
            relative = f"{SOURCE_RELATIVE_DIR}/{name}"
            try:
                record = _load_json_object(resolved)
            except WebPortfolioReadError as exc:
                if "invented" in str(exc) or "symlink" in str(exc) or "escape" in str(exc):
                    raise
                malformed += 1
                rows.append(
                    {
                        "name": name,
                        "relative": relative,
                        "expected": name in EXPECTED_FILENAMES,
                        "present": True,
                        "malformed": True,
                        "record": None,
                    }
                )
                continue
            rows.append(
                {
                    "name": name,
                    "relative": relative,
                    "expected": name in EXPECTED_FILENAMES,
                    "present": True,
                    "malformed": False,
                    "record": record,
                }
            )

    present_names = {str(row["name"]) for row in rows}
    missing_expected = sorted(EXPECTED_FILENAMES - present_names)
    return {
        "schema_version": 1,
        "portfolio_dir_relative": SOURCE_RELATIVE_DIR,
        "artifact_count": len(rows),
        "malformed_count": malformed,
        "expected_count": len(EXPECTED_FILENAMES),
        "missing_expected": missing_expected,
        "skipped_unsafe_names": skipped_names,
        "artifacts": rows,
        "materialize_invoked": False,
        "derive_invoked": False,
        "build_portfolio_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    count = view.get("artifact_count")
    artifact_count = count if isinstance(count, int) else 0
    malformed = view.get("malformed_count")
    malformed_count = malformed if isinstance(malformed, int) else 0
    if artifact_count == 0:
        return (
            "EMPTY",
            "no existing generated/portfolio artifacts; EMPTY != HEALTHY; "
            "PORTFOLIO != AUTHORITY",
            "EMPTY_PORTFOLIO_VIEW",
            False,
        )
    if malformed_count > 0:
        return (
            "UNKNOWN",
            "portfolio artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy "
            "portfolio lens",
            "UNKNOWN_PORTFOLIO_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing Layer C portfolio artifacts projected; "
        "PORTFOLIO != AUTHORITY; LAYER C != TRUTH CORE",
        "PORTFOLIO_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relative_dir": SOURCE_RELATIVE_DIR,
        "source_command": SOURCE_COMMAND,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_portfolio_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing portfolio artifacts. Never writes."""
    return _envelope(view=_existing_portfolio_artifacts(_resolve_vault(vault)))


def render_portfolio_status_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    raw_artifacts = inner.get("artifacts")
    artifacts: list[Any] = raw_artifacts if isinstance(raw_artifacts, list) else []
    lines = [
        f"atlas portfolio-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          PORTFOLIO != AUTHORITY; LAYER C != TRUTH CORE; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    for row in artifacts:
        if not isinstance(row, dict):
            continue
        raw_record = row.get("record")
        record: dict[str, Any] = raw_record if isinstance(raw_record, dict) else {}
        summary = _ascii_token(
            record.get("summary")
            or record.get("title")
            or ("malformed" if row.get("malformed") else "projected")
        )
        lines.append(f"  - {row.get('name')}: {summary or 'UNKNOWN'}")
    return "\n".join(lines) + "\n"
