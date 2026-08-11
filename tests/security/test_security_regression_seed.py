"""SECURITY ALPHA S08 — executable security regression suite SEED.

Thin presence guards only. Full adversarial suites live in remedi PRs
(#261-#265, #267) which are now on main — seed exercises those suites
(SECURITY_TESTS_SKIPPED → 0 for landed classes).

These tests:
- always validate the in-repo class registry is complete
- require remedi primary tests to be present for every registered class
- assert remedi suites declare their finding IDs (CODEX-SEC-* or SEC-*)

Never claims Codex validation complete.
Status of this seed: SECURITY_REGRESSION_SEED · AWAITING_CODEX_VALIDATION.
"""

from __future__ import annotations

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
    if finding_id in body:
        return True
    if finding_id.startswith("CODEX-") and finding_id.removeprefix("CODEX-") in body:
        return True
    return False


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
    """Require remedi suite presence + finding-ID declaration (no skip when on main)."""
    primary = _primary_present(item.primary_tests)
    assert primary is not None, _missing_reason(item)

    body = primary.read_text(encoding="utf-8")
    missing = [fid for fid in item.finding_ids if not _finding_declared(body, fid)]
    assert not missing, (
        f"{primary.as_posix()} must declare finding IDs {missing} "
        f"(SECURITY_REGRESSION_SEED guard for {item.class_id})"
    )


def test_security_regression_seed_status_banner() -> None:
    """Honesty: module docstring declares SEED + AWAITING_CODEX_VALIDATION."""
    import tests.security.test_security_regression_seed as seed_mod

    doc = seed_mod.__doc__ or ""
    assert "SECURITY_REGRESSION_SEED" in doc
    assert "AWAITING_CODEX_VALIDATION" in doc
    # Never claim Codex validation complete in the seed status banner.
    banned = "CODEX" + "_VALIDATED"
    assert banned not in doc
