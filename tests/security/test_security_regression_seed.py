"""SECURITY ALPHA S08 — executable security regression suite SEED.

Full adversarial suites live in remedi PRs (#261-#265, #267) now on main.
This seed:
- validates the in-repo class registry is complete
- requires remedi primary tests to be present for every registered class
- asserts remedi suites declare their finding IDs (CODEX-SEC-* or SEC-*)
- **executes** each registered primary suite (subprocess pytest) so a docstring
  ID alone cannot satisfy the guard (SECURITY_TESTS_SKIPPED → 0)

Never claims Codex validation complete.
Status of this seed: SECURITY_REGRESSION_SEED · AWAITING_CODEX_VALIDATION.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.security.registry import (
    REQUIRED_CLASS_IDS,
    SECURITY_REGRESSION_CLASSES,
    SecurityRegressionClass,
)

pytestmark = pytest.mark.security_regression

REPO_ROOT = Path(__file__).resolve().parents[2]


def _primary_present(paths: tuple[str, ...]) -> Path | None:
    for relative in paths:
        candidate = REPO_ROOT / relative
        if candidate.is_file():
            return candidate
    return None


def _finding_declared(body: str, finding_id: str) -> bool:
    """Accept full CODEX-SEC-NNN or abbreviated SEC-NNN forms in remedi suites."""
    abbreviated = finding_id.removeprefix("CODEX-")
    return finding_id in body or (
        finding_id.startswith("CODEX-") and abbreviated in body
    )


def _missing_reason(item: SecurityRegressionClass) -> str:
    ids = ", ".join(item.finding_ids)
    if item.remedi_pr:
        return (
            f"{ids} remedi not on main yet (PR #{item.remedi_pr}); "
            f"authoritative suite missing — class={item.class_id}"
        )
    return (
        f"{ids} remedi expected on main but primary suite missing — "
        f"class={item.class_id} paths={item.primary_tests}"
    )


def _run_primary_suite(primary: Path) -> None:
    """Execute the registered remedi suite; fail if any test fails/errors."""
    env = os.environ.copy()
    src = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (src, existing) if p)

    # Control-plane suites live outside tests/ and use their own conftest.
    cwd = REPO_ROOT
    if "atlas-vault-documentation" in primary.as_posix():
        cwd = REPO_ROOT / "atlas-vault-documentation"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(primary),
        "-q",
        "--tb=line",
        "--no-cov",
    ]
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"primary suite failed for {primary.as_posix()} "
        f"(exit={proc.returncode})\n"
        f"stdout:\n{proc.stdout[-4000:]}\n"
        f"stderr:\n{proc.stderr[-4000:]}"
    )


def test_security_regression_registry_covers_required_classes() -> None:
    """Seed invariant: every Alpha regression class remains registered."""
    expected = {
        "provenance",
        "trusted_exec",
        "root_auth",
        "path",
        "secrets",
        "request_auth",
        "capability",
        "readiness",
        "receipt",
    }
    assert expected == REQUIRED_CLASS_IDS
    assert len(SECURITY_REGRESSION_CLASSES) >= 9
    for item in SECURITY_REGRESSION_CLASSES:
        assert item.finding_ids
        assert all(fid.startswith("CODEX-SEC-") for fid in item.finding_ids)
        assert item.primary_tests
        assert item.class_id
        # Landed remediations: remedi_pr cleared so seed does not skip.
        assert item.remedi_pr is None, (
            f"{item.class_id} still points at open remedi_pr={item.remedi_pr}; "
            "clear after merge so SECURITY_TESTS_SKIPPED stays 0"
        )


@pytest.mark.parametrize(
    "item",
    SECURITY_REGRESSION_CLASSES,
    ids=[item.class_id for item in SECURITY_REGRESSION_CLASSES],
)
def test_security_regression_class_exercises_remedi_suite(
    item: SecurityRegressionClass,
) -> None:
    """Presence + finding-ID declaration + execute registered remedi suite."""
    primary = _primary_present(item.primary_tests)
    assert primary is not None, _missing_reason(item)

    body = primary.read_text(encoding="utf-8")
    missing = [fid for fid in item.finding_ids if not _finding_declared(body, fid)]
    assert not missing, (
        f"{primary.as_posix()} must declare finding IDs {missing} "
        f"(SECURITY_REGRESSION_SEED guard for {item.class_id})"
    )
    _run_primary_suite(primary)


def test_security_regression_seed_status_banner() -> None:
    """Honesty: module docstring declares SEED + AWAITING_CODEX_VALIDATION."""
    import tests.security.test_security_regression_seed as seed_mod

    doc = seed_mod.__doc__ or ""
    assert "SECURITY_REGRESSION_SEED" in doc
    assert "AWAITING_CODEX_VALIDATION" in doc
    # Never claim Codex validation complete in the seed status banner.
    banned = "CODEX" + "_VALIDATED"
    assert banned not in doc
