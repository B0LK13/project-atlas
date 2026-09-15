"""AS-2.2-ADV-POOL-001 — presence / invariant tests for 2.2 ADV matrix prep.

Docs/tests only. Does not exercise 2.1 Host/CORS/L3/ops-receipt live ADV.
Explicit: ATLAS_2_1_RELEASE_CERTIFIED = NO.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADV_POOL = REPO_ROOT / "docs" / "atlas-2.2" / "adv-pool"
MATRIX = ADV_POOL / "ADV-MATRIX.md"
INVARIANTS = ADV_POOL / "FIXTURE-INVARIANTS.md"
README = ADV_POOL / "README.md"
ADR = REPO_ROOT / "docs" / "adr" / "ADR-031-adv-pool-prep.md"
LIVE_SUITE = REPO_ROOT / "docs" / "atlas-2.1" / "ADV-LIVE-SUITE.md"

REQUIRED_SURFACES = (
    "RET",
    "CTX",
    "MEM",
    "KCI",
    "DoD",
    "TIME",
    "REALITY",
    "RESEARCH",
)

REQUIRED_ROW_PREFIXES = (
    "ADV-2.2-RET-",
    "ADV-2.2-CTX-",
    "ADV-2.2-MEM-",
    "ADV-2.2-KCI-",
    "ADV-2.2-DOD-",
    "ADV-2.2-TIME-",
    "ADV-2.2-REALITY-",
    "ADV-2.2-RESEARCH-",
)

# Synthetic shape only — must never appear as a live credential payload.
FORBIDDEN_SECRET_PATTERNS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "AKIA",
    "password=",
    "Password=",
)


def test_adv_pool_docs_exist() -> None:
    assert README.is_file()
    assert MATRIX.is_file()
    assert INVARIANTS.is_file()
    assert (ADV_POOL / "fixtures" / "README.md").is_file()
    assert ADR.is_file()


def test_adv_pool_matrix_covers_prep_surfaces() -> None:
    text = MATRIX.read_text(encoding="utf-8")
    for surface in REQUIRED_SURFACES:
        assert surface in text, f"missing surface heading token: {surface}"
    for prefix in REQUIRED_ROW_PREFIXES:
        assert prefix in text, f"missing ADV row family: {prefix}"


def test_adv_pool_fail_closed_and_no_authority_elevation() -> None:
    matrix = MATRIX.read_text(encoding="utf-8")
    invariants = INVARIANTS.read_text(encoding="utf-8")
    combined = f"{matrix}\n{invariants}"
    assert "fail-closed" in combined.lower() or "Fail-closed" in combined
    assert "authority elevation" in combined.lower() or "No authority elevation" in combined
    assert "LLM≠authority" in combined or "LLM!=authority" in combined or "LLM≠authority" in matrix
    assert "NFR-004" in combined


def test_adv_pool_release_flags_remain_no() -> None:
    for path in (README, MATRIX, ADR):
        text = path.read_text(encoding="utf-8")
        assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
        # Accept either "= NO" or "**NO**" narrative forms adjacent to the flag.
        assert (
            "ATLAS_2_1_RELEASE_CERTIFIED = NO" in text
            or "ATLAS_2_1_RELEASE_CERTIFIED` | **NO**" in text
            or "ATLAS_2_1_RELEASE_CERTIFIED = **NO**" in text
            or "`ATLAS_2_1_RELEASE_CERTIFIED` | **NO**" in text
        ), f"missing explicit NO flag in {path.name}"


def test_adv_pool_does_not_reopen_21_host_cors_l3_ops() -> None:
    matrix = MATRIX.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    combined = f"{matrix}\n{readme}"
    assert "#154" in combined
    assert "#155" in combined
    assert "Do not rewrite" in matrix or "**Do not rewrite**" in matrix
    assert "Host/CORS" in combined
    assert "ops-receipt" in combined.lower() or "OPS receipts" in combined


def test_adv_pool_fixtures_have_no_secret_material() -> None:
    fixture_root = ADV_POOL / "fixtures"
    for path in fixture_root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_SECRET_PATTERNS:
            assert pattern not in text, f"{path.name} leaks pattern {pattern!r}"
        # Disallow long hex-looking token dumps that look like real secrets.
        assert "ghp_" not in text
        assert "xoxb-" not in text


def test_adv_pool_does_not_rewrite_live_suite_rows() -> None:
    """Owned paths must not alter landed 2.1 ADV-LIVE-SUITE content."""
    assert LIVE_SUITE.is_file()
    live = LIVE_SUITE.read_text(encoding="utf-8")
    # Sanity: landed Host/CORS row still present on tip (read-only check).
    assert "ADV-2.1-20" in live
    assert "Host/CORS" in live
    # This package must not claim ownership of the live suite path.
    readme = README.read_text(encoding="utf-8")
    assert "ADV-LIVE-SUITE.md" in readme
    assert "without" in readme.lower() or "not" in readme.lower()


@pytest.mark.parametrize(
    "row_id",
    [
        "ADV-2.2-X-01",
        "ADV-2.2-X-02",
        "ADV-2.2-X-03",
        "ADV-2.2-RET-01",
        "ADV-2.2-CTX-01",
        "ADV-2.2-MEM-01",
        "ADV-2.2-KCI-01",
        "ADV-2.2-DOD-01",
        "ADV-2.2-TIME-01",
        "ADV-2.2-REALITY-01",
        "ADV-2.2-RESEARCH-01",
    ],
)
def test_adv_pool_row_ids_present(row_id: str) -> None:
    text = MATRIX.read_text(encoding="utf-8")
    assert row_id in text
