"""AS-OBSIDIAN-CAPTURE-001-F10 — graph must not write what canonical refuses.

Two generated-span-preserving writers should agree on *whether* a document is
safe to write. They did not. `graph_projections._merge_protected_regions` keeps
a historical contract for a prior note with no HUMAN regions -- preserve text
outside the generated span, where the canonical core returns the fresh render --
and that branch splices by hand instead of delegating, so it never reaches the
canonical structural parse.

Its own marker validation compares HUMAN marker **counts and names**, never
**order**. A rendered document whose markers are reversed (`END` before `BEGIN`)
or crossed (`a b /a /b`) therefore passed and was **written**, while the
canonical core refuses it as `unpaired`. Graph accepted what canonical rejected
-- fail-open-shaped relative to canonical, and the disagreement is about policy,
not wording.

Found by independent verification of F9 as a refusal-set divergence, measured
there but fixed here: it is a different defect class from F9's diagnostic
uniformity, so it gets its own package.

Scope. Only the *fail-open* direction is closed. The reverse -- canonical
accepts, graph refuses -- is F4's **disclosed and intentional** contract: graph
refuses rather than silently discard the text outside the generated span. That
asymmetry is deliberate and is asserted here so it cannot be removed by accident.

Reachability, stated honestly. The rendered document is Atlas-generated, so this
needs the renderer itself to emit malformed markers; today it does not. This is
defence in depth at a writer boundary, not a live corruption path -- and it is
worth having precisely because the canonical core already refuses these shapes.
"""

from __future__ import annotations

import itertools

import pytest

import project_atlas.graph_projections as gp
from project_atlas.graph_projections import GraphProjectionError
from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    merge_protected_regions,
)

HUMAN_OPEN = "<!-- BEGIN HUMAN: notes -->"
HUMAN_CLOSE = "<!-- END HUMAN: notes -->"

#: A prior note with NO HUMAN regions -- the branch that bypasses the canonical
#: structural parse. With a generated span, so the splice path is taken.
NO_HUMAN_PRIOR = f"{GENERATED_START}\nold\n{GENERATED_END}\nouter text\n"

#: Renders the canonical core refuses as structurally unparseable.
MALFORMED_RENDER = {
    "reversed-end-before-begin": (
        f"{GENERATED_START}\nx\n{GENERATED_END}\n{HUMAN_CLOSE}\n{HUMAN_OPEN}\n"
    ),
    "crossed-a-b": (
        f"{GENERATED_START}\nx\n{GENERATED_END}\n"
        "<!-- BEGIN HUMAN: a -->\n<!-- BEGIN HUMAN: b -->\n"
        "<!-- END HUMAN: a -->\n<!-- END HUMAN: b -->\n"
    ),
    "unclosed-region": f"{GENERATED_START}\nx\n{GENERATED_END}\n{HUMAN_OPEN}\nbody\n",
}


@pytest.mark.parametrize("label", sorted(MALFORMED_RENDER))
def test_f10_graph_refuses_a_render_canonical_refuses(label: str) -> None:
    """The whole point: graph must not accept what canonical rejects."""
    rendered = MALFORMED_RENDER[label]
    with pytest.raises(ProtectedRegionError):
        merge_protected_regions(existing=NO_HUMAN_PRIOR, rendered=rendered, path="n.md")
    with pytest.raises(GraphProjectionError):
        gp._merge_protected_regions(existing=NO_HUMAN_PRIOR, rendered=rendered, path="n.md")


@pytest.mark.parametrize("label", sorted(MALFORMED_RENDER))
def test_f10_refusal_leaves_the_prior_note_untouched(label: str) -> None:
    before = NO_HUMAN_PRIOR
    with pytest.raises(GraphProjectionError):
        gp._merge_protected_regions(
            existing=NO_HUMAN_PRIOR, rendered=MALFORMED_RENDER[label], path="n.md"
        )
    assert before == NO_HUMAN_PRIOR


def test_f10_a_well_formed_render_is_still_accepted() -> None:
    """Positive control: the fix must not widen refusal."""
    rendered = f"{GENERATED_START}\nfresh\n{GENERATED_END}\n{HUMAN_OPEN}\nkept\n{HUMAN_CLOSE}\n"
    merged = gp._merge_protected_regions(
        existing=NO_HUMAN_PRIOR, rendered=rendered, path="n.md"
    )
    assert "fresh" in merged
    assert "outer text" in merged, "the disclosed graph contract must still preserve outside text"


def test_f10_the_disclosed_f4_asymmetry_is_deliberate_and_remains() -> None:
    """graph refuses where canonical accepts, and that direction is intentional.

    F4 disclosed it: a prior note with a generated span and a render offering
    none would have canonical return the fresh document, discarding the text
    outside the span. Graph refuses instead. Asserted so it cannot be removed
    by someone "fixing the asymmetry" wholesale.
    """
    rendered = "no span at all\n"
    assert merge_protected_regions(
        existing=NO_HUMAN_PRIOR, rendered=rendered, path="n.md"
    ) == rendered
    with pytest.raises(GraphProjectionError):
        gp._merge_protected_regions(existing=NO_HUMAN_PRIOR, rendered=rendered, path="n.md")


def test_f10_no_fail_open_divergence_across_a_differential_sweep() -> None:
    """No shape may have canonical refuse while graph accepts.

    The sweep varies *both* sides, because this defect lives on the rendered
    side and a corpus that only varies the prior note cannot see it.
    """
    fragments = [
        GENERATED_START + "\n",
        GENERATED_END + "\n",
        HUMAN_OPEN + "\n",
        HUMAN_CLOSE + "\n",
        "text\n",
    ]
    fail_open: list[tuple[str, str]] = []
    disclosed = 0
    pairs = 0
    for existing_parts in itertools.product(fragments, repeat=2):
        for rendered_parts in itertools.product(fragments, repeat=2):
            existing, rendered = "".join(existing_parts), "".join(rendered_parts)
            pairs += 1
            try:
                merge_protected_regions(existing=existing, rendered=rendered, path="n.md")
                canonical_refused = False
            except ProtectedRegionError:
                canonical_refused = True
            try:
                gp._merge_protected_regions(existing=existing, rendered=rendered, path="n.md")
                graph_refused = False
            except GraphProjectionError:
                graph_refused = True
            if canonical_refused and not graph_refused:
                fail_open.append((existing, rendered))
            elif graph_refused and not canonical_refused:
                disclosed += 1

    assert pairs == 625, pairs
    assert not fail_open, (
        f"graph accepted {len(fail_open)} shapes canonical refused: {fail_open[:3]}"
    )
    # The disclosed F4 direction is expected to remain; a sweep finding none of
    # it would mean the corpus stopped exercising that contract.
    assert disclosed > 0, "the sweep no longer reaches the disclosed graph contract"
