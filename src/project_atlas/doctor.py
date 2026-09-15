"""PROD-DOCTOR-001: ``atlas doctor`` environment / Vault self-diagnosis.

Read-only, offline, deterministic health checks over the runtime environment
and (optionally) a target Vault. The command reports objective signals only --
never a subjective trust score (see AGENTS.md) -- and treats absent evidence as
``unknown`` rather than healthy (unknown != healthy).

Exit-code contract, surfaced by the CLI:

- 0: no ERROR checks (OK, WARN, or UNKNOWN only);
- 1: at least one ERROR check.

The module is intentionally dependency-light and side-effect free: it never
writes to disk and never mutates the Vault, so it is safe to run at any time.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Literal

from project_atlas import __version__
from project_atlas.config import AtlasConfig
from project_atlas.schema import available_schemas

Status = Literal["ok", "warn", "error", "unknown"]

# Rollup precedence: error > warn > unknown > ok (unknown is never "healthy").
_SEVERITY: dict[Status, int] = {"ok": 0, "unknown": 1, "warn": 2, "error": 3}

_LABEL: dict[Status, str] = {
    "ok": "PASS",
    "warn": "WARN",
    "error": "FAIL",
    "unknown": "UNKNOWN",
}

MIN_PYTHON: tuple[int, int] = (3, 12)

# Runtime dependencies declared in pyproject [project].dependencies.
# Names are matched case-insensitively by importlib.metadata (PEP 503).
_REQUIRED_DISTRIBUTIONS: tuple[str, ...] = ("pydantic", "PyYAML", "jsonschema")


@dataclass(frozen=True)
class Check:
    """A single objective diagnostic signal."""

    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Ordered, deterministic collection of diagnostic checks."""

    checks: tuple[Check, ...]

    @property
    def rollup(self) -> Status:
        """Worst status across all checks (error > warn > unknown > ok)."""
        worst: Status = "ok"
        for check in self.checks:
            if _SEVERITY[check.status] > _SEVERITY[worst]:
                worst = check.status
        return worst

    @property
    def ok(self) -> bool:
        """True when no check is an ERROR; WARN and UNKNOWN are non-fatal."""
        return all(check.status != "error" for check in self.checks)


def _check_python() -> Check:
    info = sys.version_info
    version = f"{info.major}.{info.minor}.{info.micro}"
    if (info.major, info.minor) >= MIN_PYTHON:
        return Check("python-runtime", "ok", f"Python {version} (>= 3.12)")
    return Check("python-runtime", "error", f"Python {version} (< 3.12 required)")


def _check_package() -> Check:
    return Check("atlas-package", "ok", f"project-atlas {__version__}")


def _check_dependencies() -> list[Check]:
    checks: list[Check] = []
    for dist in _REQUIRED_DISTRIBUTIONS:
        try:
            installed = metadata.version(dist)
        except metadata.PackageNotFoundError:
            checks.append(Check(f"dependency:{dist}", "error", f"{dist} not installed"))
        else:
            checks.append(Check(f"dependency:{dist}", "ok", f"{dist} {installed}"))
    return checks


def _check_schemas() -> Check:
    try:
        schemas = available_schemas()
    except (OSError, ValueError, ImportError) as exc:
        return Check("package-data:schemas", "error", f"schema resources unreadable: {exc}")
    if schemas:
        return Check("package-data:schemas", "ok", f"{len(schemas)} JSON schemas shipped")
    return Check("package-data:schemas", "error", "no JSON schemas found in package data")


def _check_config(config: AtlasConfig) -> Check:
    # The caller already loaded the config; presence of nested models confirms it.
    return Check("configuration", "ok", f"loaded (log_format={config.logging.format})")


def _check_vault(vault: Path) -> list[Check]:
    if not vault.exists():
        # Absent evidence stays unknown -- never reported as healthy.
        return [Check("vault:present", "unknown", f"vault path absent: {vault}")]
    if not vault.is_dir():
        return [Check("vault:present", "error", f"vault path is not a directory: {vault}")]

    checks: list[Check] = [Check("vault:present", "ok", f"vault directory: {vault}")]
    # Core scaffold artifacts (AT-001).
    for rel in ("index.md", "00-system/vault-charter.md"):
        if (vault / rel).is_file():
            checks.append(Check(f"vault:{rel}", "ok", "present"))
        else:
            checks.append(Check(f"vault:{rel}", "warn", "missing (run `atlas init`)"))
    # Generated indexes: absent is unknown (needs `atlas build-indexes`), not unhealthy.
    if (vault / "generated" / "indexes").is_dir():
        checks.append(Check("vault:generated-indexes", "ok", "present"))
    else:
        checks.append(
            Check("vault:generated-indexes", "unknown", "absent (run `atlas build-indexes`)")
        )
    return checks


def run_doctor(config: AtlasConfig, vault: Path | None = None) -> DoctorReport:
    """Run all diagnostics deterministically and return an ordered report."""
    checks: list[Check] = [
        _check_python(),
        _check_package(),
        *_check_dependencies(),
        _check_schemas(),
        _check_config(config),
    ]
    if vault is not None:
        checks.extend(_check_vault(vault))
    return DoctorReport(checks=tuple(checks))


def render_text(report: DoctorReport) -> str:
    """Human-readable, ASCII-only rendering (stdout-safe, deterministic)."""
    lines = ["atlas doctor - environment self-check (objective signals; unknown != healthy)"]
    for check in report.checks:
        lines.append(f"  [{_LABEL[check.status]}] {check.name}: {check.detail}")
    lines.append(f"rollup: {report.rollup}")
    return "\n".join(lines)


def to_dict(report: DoctorReport) -> dict[str, object]:
    """Machine-readable report; JSON-serializable with sort_keys=True."""
    return {
        "rollup": report.rollup,
        "ok": report.ok,
        "checks": [
            {"name": check.name, "status": check.status, "detail": check.detail}
            for check in report.checks
        ],
    }
