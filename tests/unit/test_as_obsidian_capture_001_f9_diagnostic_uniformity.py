"""AS-OBSIDIAN-CAPTURE-001-F9 — one marker diagnosis, whichever writer refuses.

A generated-marker collision is the same operator condition no matter which
generated-span-preserving writer reaches the note first. Before this package it
did not read that way. The identical corrupt note produced

    canonical : malformed-generated-markers:count,begin=2,end=1,expected=1,no-write:n.md
    graph     : malformed-generated-markers:n.md

so what an operator was told about their own note depended on an internal
routing detail they cannot see: which surface happened to touch it. The five
bare sites in ``graph_projections`` now emit the canonical diagnosis.

Scope. This is a diagnostic change, not a policy change: exactly the same notes
are refused, with the same fail-closed guarantee and the same bytes left on
disk. The message *prefix* is unchanged, so every existing assertion matching
``malformed-generated-markers`` keeps passing.

Out of scope and owner-gated: ``ingestion.py`` raises a plain ``ValueError`` at
three sites with a different spelling again ("malformed generated markers",
spaces not hyphens) and no diagnosis at all. It is a certified surface frozen by
``test_atlas3_demo_isolation_001``; changing it needs an owner-approved
sha256-pinned exception under ``docs/atlas-3/ARCHITECTURE.md`` §9.1, which this
lane cannot self-grant. Those sites are recorded as a residual, not fixed here.
"""

from __future__ import annotations

import pytest

import project_atlas.graph_projections as gp
from project_atlas.graph_projections import GraphProjectionError
from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    merge_protected_regions,
)


def _note(human_body: str = "") -> str:
    return (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n\n"
        f"<!-- BEGIN HUMAN: notes -->\n{human_body}<!-- END HUMAN: notes -->\n"
    )


_FRESH = _note()

#: Corrupt shapes reachable through both writers. The value is the reason token
#: the diagnosis must carry.
CORRUPT = {
    "duplicate-begin": (f"{GENERATED_START}\na\n{GENERATED_START}\nb\n{GENERATED_END}\n", "count"),
    "begin-without-end": (f"{GENERATED_START}\nbody\n", "count"),
    "end-without-begin": (f"{GENERATED_END}\nbody\n", "count"),
    "end-before-begin": (f"{GENERATED_END}\na\n{GENERATED_START}\n", "end-before-begin"),
}


def _canonical_message(existing: str) -> str:
    with pytest.raises(ProtectedRegionError) as caught:
        merge_protected_regions(existing=existing, rendered=_FRESH, path="n.md")
    return str(caught.value)


def _graph_message(existing: str) -> str:
    with pytest.raises(GraphProjectionError) as caught:
        gp._merge_protected_regions(existing=existing, rendered=_FRESH, path="n.md")
    return str(caught.value)


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_graph_and_canonical_agree_exactly(label: str) -> None:
    """The whole point: byte-identical diagnosis from either surface."""
    existing, _ = CORRUPT[label]
    assert _graph_message(existing) == _canonical_message(existing)


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_graph_reports_the_reason(label: str) -> None:
    existing, reason = CORRUPT[label]
    assert _graph_message(existing).startswith(f"malformed-generated-markers:{reason},")


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_graph_reports_observable_counts(label: str) -> None:
    existing, _ = CORRUPT[label]
    message = _graph_message(existing)
    begins = existing.count(GENERATED_START)
    ends = existing.count(GENERATED_END)
    assert f"begin={begins}" in message
    assert f"end={ends}" in message
    assert "expected=1" in message


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_graph_states_that_nothing_was_written(label: str) -> None:
    """`no-write` is the most useful fact an operator gets from a refusal."""
    existing, _ = CORRUPT[label]
    assert "no-write" in _graph_message(existing)


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_refusal_still_leaves_the_note_byte_identical(label: str) -> None:
    """A richer message must not come with a weaker fail-closed guarantee."""
    existing, _ = CORRUPT[label]
    before = existing
    with pytest.raises(GraphProjectionError):
        gp._merge_protected_regions(existing=existing, rendered=_FRESH, path="n.md")
    assert existing == before


@pytest.mark.parametrize("label", sorted(CORRUPT))
def test_f9_prefix_is_unchanged_so_existing_assertions_still_match(label: str) -> None:
    """Backward compatibility is load-bearing: other suites match this prefix."""
    existing, _ = CORRUPT[label]
    assert _graph_message(existing).startswith("malformed-generated-markers:")


def test_f9_reserved_marker_in_human_region_is_reported_by_graph_too() -> None:
    """F3's containment fact must not be canonical-only."""
    existing = _note(f"I document the {GENERATED_START} marker here.\n")
    message = _graph_message(existing)
    assert "reserved-marker-in-human-region" in message
    assert message == _canonical_message(existing)


def test_f9_rendered_without_a_generated_span_is_not_mislabelled() -> None:
    """A distinct condition gets a distinct reason.

    This site refuses because the *fresh render* offers no generated span to
    substitute -- an Atlas-side condition, not a corrupt note. Reporting it as
    a marker malformation of the operator's file would point them at the wrong
    artifact entirely. It reaches this branch only for a prior note with no
    HUMAN regions, which is the graph-specific contract F4 disclosed.
    """
    existing = f"{GENERATED_START}\nold\n{GENERATED_END}\nouter text\n"
    with pytest.raises(GraphProjectionError) as caught:
        gp._merge_protected_regions(existing=existing, rendered="no span here\n", path="n.md")
    message = str(caught.value)
    assert "rendered-has-no-generated-span" in message
    assert "count" not in message.split(":")[1].split(",")[0]
    assert "no-write" in message


def test_f9_a_well_formed_note_is_untouched_by_any_of_this() -> None:
    """Positive control: the diagnosis path must not have widened refusal."""
    existing = _note("human words\n")
    merged = gp._merge_protected_regions(existing=existing, rendered=_FRESH, path="n.md")
    assert "human words" in merged


# --- the defensive guard inside _generated_span -------------------------------
#
# This site is UNREACHABLE through `_merge_protected_regions`:
# `_validate_protected_markers` runs first, on both `existing` and `rendered`,
# and already refuses every shape that would trigger it. It is a defence in
# depth for direct callers, so it is pinned by direct calls -- which is the only
# way to pin it at all.
#
# Recorded because it was found the honest way: reverting this site to the bare
# message left the F9 suite at 27 passed, i.e. the controls proved the tests
# were NOT load-bearing here. These four tests are what make controls C and E
# bite.

_SPAN_ONLY = {
    "begin-without-end": (f"{GENERATED_START}\nbody\n", "count", 1, 0),
    "end-without-begin": (f"{GENERATED_END}\nbody\n", "count", 0, 1),
    "end-before-begin": (f"{GENERATED_END}\na\n{GENERATED_START}\n", "end-before-begin", 1, 1),
}


@pytest.mark.parametrize("label", sorted(_SPAN_ONLY))
def test_f9_generated_span_guard_reports_its_reason(label: str) -> None:
    text, reason, begins, ends = _SPAN_ONLY[label]
    with pytest.raises(GraphProjectionError) as caught:
        gp._generated_span(text, path="n.md")
    message = str(caught.value)
    assert message.startswith(f"malformed-generated-markers:{reason},")
    assert f"begin={begins}" in message
    assert f"end={ends}" in message
    assert "no-write" in message


def test_f9_generated_span_guard_distinguishes_order_from_absence() -> None:
    """`end-before-begin` and `count` are different operator conditions.

    Collapsing both to `count` loses the distinction an operator would act on,
    and no public-path test can catch that -- this guard is unreachable through
    `_merge_protected_regions`.
    """
    with pytest.raises(GraphProjectionError) as absent:
        gp._generated_span(f"{GENERATED_START}\nb\n", path="n.md")
    with pytest.raises(GraphProjectionError) as reversed_order:
        gp._generated_span(f"{GENERATED_END}\na\n{GENERATED_START}\n", path="n.md")
    missing = str(absent.value)
    misordered = str(reversed_order.value)
    assert "count" in missing.split(":")[1]
    assert "end-before-begin" in misordered.split(":")[1]
    assert missing != misordered


def test_f9_generated_span_returns_none_when_there_is_no_span() -> None:
    """Positive control: absence of markers is not an error."""
    assert gp._generated_span("plain text\n", path="n.md") is None
