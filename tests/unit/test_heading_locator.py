"""Unit tests for heading-locator collision remediation (AS-EXT-001A, §7.7)."""

from __future__ import annotations

from pathlib import Path

from project_atlas.claim_identity import extract_claims

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "as-ext-001a"


def _tuples(claims: list[dict]) -> list[tuple[str, str, str]]:
    return [(str(c["claim_type"]), str(c["field"]), str(c["locator"])) for c in claims]


def test_default_locator_unchanged_for_non_colliding_docs() -> None:
    """Backward compatibility: nearest-heading slug stays the default."""
    claims = extract_claims("## Package summary\n\nstatus: certified\n")
    assert _tuples(claims) == [("roadmap-status", "roadmap", "heading:package-summary")]


def test_true_duplicates_collapse_deterministically() -> None:
    """The same statement repeated is one claim, keep-first (§7.7)."""
    text = "## Summary\n\nstatus: certified\n\nstatus: certified\n"
    claims = extract_claims(text, reject_unresolved=True)
    assert _tuples(claims) == [("roadmap-status", "roadmap", "heading:summary")]


def test_full_heading_path_resolves_different_parents() -> None:
    """F-07: repeated same-titled headings under different parents."""
    text = (
        "## Phase 0 — Foundation\n\n### Objective\n\nstatus: active\n\n"
        "## Phase 1 — Discovery\n\n### Objective\n\nstatus: planned\n"
    )
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    locators = sorted(str(c["locator"]) for c in claims)
    assert locators == [
        "headingpath:phase-0-foundation/objective",
        "headingpath:phase-1-discovery/objective",
    ]


def test_ordinal_suffix_resolves_identical_paths() -> None:
    """Repeated sibling statements under one heading: deterministic ordinals."""
    text = "# Title\n\nstatus: decided\n\nstatus: superseded\n"
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    assert _tuples(claims) == [
        ("roadmap-status", "roadmap", "heading:title~1"),
        ("roadmap-status", "roadmap", "heading:title~2"),
    ]
    # Deterministic repeat: byte-identical record ordering and locators.
    again = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    assert _tuples(claims) == _tuples(again)


def test_verify_markdown_fallback_no_longer_aborts() -> None:
    """Collision fixture one: repeated status keys resolve without abort (§10)."""
    text = (FIXTURES / "real" / "f01-verify-structured-document.md").read_text(encoding="utf-8")
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    status_claims = [c for c in claims if c["field"] == "roadmap"]
    assert len(status_claims) == 3
    locators = [str(c["locator"]) for c in status_claims]
    assert len(set(locators)) == 3
    assert not any(c.get("withheld") for c in claims)


def test_foreign_h1_collision_no_longer_aborts() -> None:
    """Collision fixture two (F-08): duplicated foreign H1 disambiguated (§10)."""
    text = (FIXTURES / "real" / "f08-plan-foreign-h1-excerpt.md").read_text(encoding="utf-8")
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    rerun = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    assert _tuples(claims) == _tuples(rerun)
    tuples = _tuples([c for c in claims if not c.get("withheld")])
    assert len(tuples) == len(set(tuples))


def test_real_plan_md_extracts_without_abort() -> None:
    """The full P0 collision file extracts end-to-end without raising."""
    plan = Path(__file__).resolve().parents[2] / "docs" / "plan.md"
    claims = extract_claims(
        plan.read_text(encoding="utf-8"), reject_unresolved=True, withhold_unresolvable=True
    )
    tuples = _tuples([c for c in claims if not c.get("withheld")])
    assert len(tuples) == len(set(tuples))


def test_duplicate_explicit_ids_withheld_not_rewritten() -> None:
    """Duplicate explicit IDs are withheld, never ordinal-qualified (§7.7)."""
    text = "## A\n\nstatus: certified {#dup}\n\n## B\n\nstatus: superseded {#dup}\n"
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    assert len(claims) == 2
    assert all(c.get("withheld") for c in claims)
    assert all(c["locator"] == "id:dup" for c in claims)


def test_legacy_behavior_preserved_without_withhold_flag() -> None:
    """Without the flag, colliding records pass through for the existing
    fail-closed compiler path (migration/compiler parity)."""
    text = "# Title\n\nstatus: decided\n\nstatus: superseded\n"
    claims = extract_claims(text, reject_unresolved=True)
    assert [str(c["locator"]) for c in claims] == ["heading:title~1", "heading:title~2"]
    assert not any(c.get("withheld") for c in claims)


def test_no_safe_locator_withholds_without_aborting_others() -> None:
    """§7.7: withhold + diagnostic path must not abort independent extraction."""
    text = (
        "## A\n\nstatus: certified {#dup}\n\n"
        "## B\n\nstatus: superseded {#dup}\n\n"
        "## C\n\ndecision: proceed\n"
    )
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    independent = [c for c in claims if not c.get("withheld")]
    assert _tuples(independent) == [("decision", "decision", "heading:c")]
    assert sum(1 for c in claims if c.get("withheld")) == 2


def test_resolution_is_smallest_stable_change() -> None:
    """Mixed doc: only the colliding group is re-scoped; other locators keep
    the legacy nearest-heading form byte-identically."""
    text = (
        "## Overview\n\ndecision: proceed\n\n"
        "# Nebula Control Platform\n\nstatus: certified\n\n"
        "# Nebula Control Platform\n\nstatus: superseded\n"
    )
    claims = extract_claims(text, reject_unresolved=True, withhold_unresolvable=True)
    by_field = {str(c["field"]): c for c in claims}
    assert by_field["decision"]["locator"] == "heading:overview"
    assert by_field["roadmap"]["locator"].startswith("heading:nebula-control-platform")
