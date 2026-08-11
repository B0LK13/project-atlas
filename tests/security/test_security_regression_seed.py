"""SECURITY ALPHA S08 — executable security regression suite SEED.

Thin presence guards only. Full adversarial suites live in remedi PRs
(#261-#265, S02) and must not be duplicated here.

These tests:
- always validate the in-repo class registry is complete
- skip with an explicit CODEX-SEC / PR reason until remedi tests land on main
- once remedi tests are present, assert they still declare their finding IDs

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


def _skip_reason(item: SecurityRegressionClass) -> str:
    ids = ", ".join(item.finding_ids)
    if item.remedi_pr:
        return (
            f"{ids} remedi not on main yet (PR #{item.remedi_pr}); "
            f"authoritative suite pending merge — class={item.class_id}"
        )
    return (
        f"{ids} remedi still landing (S02 / open Alpha remedi); "
        f"authoritative suite pending merge — class={item.class_id}"
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


@pytest.mark.parametrize(
    "item",
    SECURITY_REGRESSION_CLASSES,
    ids=[item.class_id for item in SECURITY_REGRESSION_CLASSES],
)
def test_security_regression_class_pending_or_declared(
    item: SecurityRegressionClass,
) -> None:
    """Skip until remedi suite lands; then require finding-ID declaration."""
    primary = _primary_present(item.primary_tests)
    if primary is None:
        pytest.skip(_skip_reason(item))

    body = primary.read_text(encoding="utf-8")
    missing = [fid for fid in item.finding_ids if fid not in body]
    assert not missing, (
        f"{primary.as_posix()} must declare finding IDs {missing} "
        f"(SECURITY_REGRESSION_SEED guard for {item.class_id})"
    )


def test_security_regression_seed_status_banner() -> None:
    """Honesty: seed docstring declares SEED + AWAITING_CODEX_VALIDATION."""
    text = Path(__file__).read_text(encoding="utf-8")
    assert "SECURITY_REGRESSION_SEED" in text
    assert "AWAITING_CODEX_VALIDATION" in text
