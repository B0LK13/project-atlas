"""Regression tests for the capability-maturity-scoped 2.2 prep guard.

GOVERNANCE_GUARD_RECONCILIATION (D-INTEGRATE-007A). These prove BOTH sides of the
reconciled boundary:

* ALLOW — an implementation-unlocked capability's branch MAY touch its own
  production surface without tripping the guard.
* DENY — a prep-frozen package's branch may NOT touch its production surface
  (fails closed), and the historical false positive (any ``src/`` change on any
  2.2 branch red-flagging clean CI) is gone.
"""

from __future__ import annotations

import pytest
from _atlas_2_2_maturity import (
    IMPLEMENTATION_UNLOCKED,
    KNOWN_MATURITIES,
    PREP_FROZEN,
    ROOT,
    assert_prep_branch_scope,
    branch_changes,
    is_unlocked,
    load_maturity,
    package_entry,
    production_surface,
    surface_violations,
)

UNIT = ROOT / "tests" / "unit"

FROZEN_WITH_SURFACE = {
    "conflict-ux": "src/project_atlas/conflict_projections.py",
    "chatgpt-live": "src/project_atlas/chatgpt_bridge.py",
    "compat-pin": "src/project_atlas/compat_anchor.py",
    "reality-live": "src/project_atlas/reality_gap.py",
}

UNLOCKED_SURFACE = {
    "ask-atlas-2": "src/project_atlas/ask_atlas_live.py",
    "time-machine": "src/project_atlas/bitemporal.py",
    "ret-hybrid": "src/project_atlas/hybrid_retrieval.py",
    "ctx-compiler": "src/project_atlas/context_pack_composition.py",
    "runtime-001": "src/project_atlas/runtime_22.py",
    "eval-matrix": "src/project_atlas/eval_substrate.py",
}


def _packages() -> dict[str, dict[str, object]]:
    return load_maturity()["packages"]  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# ALLOW: implementation-unlocked capabilities may mutate their own surface.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("package", "src_path"), sorted(UNLOCKED_SURFACE.items()))
def test_allow_unlocked_capability_may_touch_own_surface(package: str, src_path: str) -> None:
    assert is_unlocked(package)
    # A branch that ships this capability's runtime code must NOT trip the guard.
    assert_prep_branch_scope(package, changed={src_path, "docs/atlas-2.2/notes.md"})


def test_allow_unlocked_branch_touching_many_src_files() -> None:
    """A real feature branch shipping several unlocked src files passes ALLOW."""
    changed = {
        "src/project_atlas/ask_atlas_live.py",
        "src/project_atlas/hybrid_retrieval.py",
        "src/project_atlas/eval_substrate.py",
        "tests/unit/test_as_2_2_ask2_deepen_prep_001.py",
    }
    assert_prep_branch_scope("ask-atlas-2", changed=changed)


# --------------------------------------------------------------------------- #
# DENY: prep-frozen packages may NOT mutate their production surface.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("package", "src_path"), sorted(FROZEN_WITH_SURFACE.items()))
def test_deny_frozen_package_may_not_touch_own_surface(package: str, src_path: str) -> None:
    assert not is_unlocked(package)
    # Simulated frozen-prep src mutation must fail closed.
    with pytest.raises(AssertionError, match="must not mutate its production surface"):
        assert_prep_branch_scope(package, changed={src_path})


def test_deny_reports_offending_paths() -> None:
    with pytest.raises(AssertionError, match=r"conflict_projections\.py"):
        assert_prep_branch_scope(
            "conflict-ux",
            changed={"src/project_atlas/conflict_projections.py", "docs/x.md"},
        )


# --------------------------------------------------------------------------- #
# No false positive: the old blanket "no src/ on any 2.2 branch" rule is gone.
# --------------------------------------------------------------------------- #
def test_frozen_guard_ignores_unrelated_src_changes() -> None:
    """A frozen package must NOT trip on another capability's src changes."""
    unlocked_src = {path for path in UNLOCKED_SURFACE.values()}
    for package in FROZEN_WITH_SURFACE:
        # None of the unlocked surfaces are this frozen package's surface.
        assert_prep_branch_scope(package, changed=set(unlocked_src))


def test_every_frozen_guard_passes_on_unlocked_feature_branch() -> None:
    """Simulate the historical red-flag scenario: a branch shipping 2.2 src.

    Every prep-frozen package's guard must pass because it only owns its own
    surface now, not a blanket ``src/`` veto.
    """
    feature_branch = {
        "src/project_atlas/ask_atlas_live.py",
        "src/project_atlas/hybrid_retrieval.py",
        "src/project_atlas/context_pack_composition.py",
        "src/project_atlas/runtime_22.py",
        "src/project_atlas/eval_substrate.py",
    }
    for package, entry in _packages().items():
        if entry["maturity"] == PREP_FROZEN:
            assert_prep_branch_scope(package, changed=set(feature_branch))


def test_frozen_empty_surface_never_denies() -> None:
    empty = [p for p, e in _packages().items() if not production_surface(p) and not is_unlocked(p)]
    assert empty, "expected some frozen packages with no dedicated 2.2 surface"
    for package in empty:
        assert_prep_branch_scope(package, changed={"src/project_atlas/anything.py"})


# --------------------------------------------------------------------------- #
# Directory-prefix surface matching.
# --------------------------------------------------------------------------- #
def test_surface_directory_prefix_match() -> None:
    changed_hit = {"src/project_atlas/web_api/handler.py"}
    assert surface_violations("conflict-ux", changed_hit) == []
    # Prefix entries (ending in '/') match any file beneath them.
    changed = {"src/project_atlas/conflict_projections.py"}
    assert surface_violations("conflict-ux", changed) == [
        "src/project_atlas/conflict_projections.py"
    ]


# --------------------------------------------------------------------------- #
# Maturity data integrity.
# --------------------------------------------------------------------------- #
def test_unknown_package_fails_closed() -> None:
    with pytest.raises(AssertionError, match=r"unknown 2\.2 package"):
        package_entry("does-not-exist")


def test_maturity_values_are_known() -> None:
    for package, entry in _packages().items():
        assert entry["maturity"] in KNOWN_MATURITIES, package


def test_declared_guard_tests_exist_and_import_helper() -> None:
    for package, entry in _packages().items():
        for rel in entry.get("guard_tests", []):  # type: ignore[union-attr]
            path = ROOT / rel
            assert path.is_file(), f"{package}: missing guard test {rel}"
            assert "assert_prep_branch_scope" in path.read_text(encoding="utf-8"), rel


def test_every_guard_bearing_test_is_mapped() -> None:
    """Any test importing the shared guard must reference a known package."""
    packages = _packages()
    mapped: set[str] = set()
    for entry in packages.values():
        for rel in entry.get("guard_tests", []):  # type: ignore[union-attr]
            mapped.add(rel)
    for path in sorted(UNIT.glob("test_as_2_2_*prep_001.py")):
        text = path.read_text(encoding="utf-8")
        if "assert_prep_branch_scope" not in text:
            continue
        rel = path.relative_to(ROOT).as_posix()
        assert rel in mapped, f"guard test {rel} not mapped in PACKAGE-MATURITY.json"
        pkg = text.split('assert_prep_branch_scope("', 1)[1].split('"', 1)[0]
        assert pkg in packages, f"{rel} references unknown package {pkg!r}"


def test_at_least_one_unlocked_and_one_frozen() -> None:
    maturities = {e["maturity"] for e in _packages().values()}
    assert IMPLEMENTATION_UNLOCKED in maturities
    assert PREP_FROZEN in maturities


# --------------------------------------------------------------------------- #
# The guard is satisfied on THIS branch (self-consistency).
# --------------------------------------------------------------------------- #
def test_this_branch_touches_no_frozen_surface() -> None:
    changed = branch_changes()
    for package, entry in _packages().items():
        if entry["maturity"] == PREP_FROZEN:
            assert surface_violations(package, changed) == [], package
