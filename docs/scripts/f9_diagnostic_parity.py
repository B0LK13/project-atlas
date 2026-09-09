r"""Differential harness for AS-OBSIDIAN-CAPTURE-001-F9 diagnosis parity.

F9's claim is that a generated-marker collision produces the *same* message
whichever generated-span-preserving writer refuses it, so an operator's
diagnosis no longer depends on which surface reached their note first. Before
F9 the identical corrupt note gave::

    canonical : malformed-generated-markers:count,begin=2,end=1,expected=1,no-write:n.md
    graph     : malformed-generated-markers:n.md

This script exists because the seal cited that parity from verification reports
that are session artifacts and are **not in this repository**. Review raised
that as a P1: a clean checkout could not reproduce or audit the evidence behind
a sealed backlog entry. An instrument described is not an instrument available,
so here is the instrument.

It reports two things:

* **parity** -- for every shape in a fixed corpus plus a generated sweep, the
  two surfaces are compared byte for byte, counting agreements and divergences;
* **refusal-set stability** -- whether each shape is accepted or refused, so a
  future change that silently widens or narrows what is refused shows up as a
  policy delta rather than only as a message delta.

Run it on any checkout::

    python docs/scripts/f9_diagnostic_parity.py

Exit 0 when every shape agrees; 1 otherwise, naming each divergence.
"""

from __future__ import annotations

import itertools

from project_atlas.graph_projections import GraphProjectionError
from project_atlas.graph_projections import _merge_protected_regions as graph_merge
from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    merge_protected_regions,
)

HUMAN_OPEN = "<!-- BEGIN HUMAN: notes -->"
HUMAN_CLOSE = "<!-- END HUMAN: notes -->"


def note(human_body: str = "") -> str:
    return (
        f"{GENERATED_START}\ngenerated body\n{GENERATED_END}\n\n"
        f"{HUMAN_OPEN}\n{human_body}{HUMAN_CLOSE}\n"
    )


FRESH = note()

#: Shapes named in the F9 evidence record, including two the package's own
#: tests do not cover (triple begin, balanced forged pair).
NAMED: dict[str, str] = {
    "duplicate-begin": f"{GENERATED_START}\na\n{GENERATED_START}\nb\n{GENERATED_END}\n",
    "begin-without-end": f"{GENERATED_START}\nbody\n",
    "end-without-begin": f"{GENERATED_END}\nbody\n",
    "end-before-begin": f"{GENERATED_END}\na\n{GENERATED_START}\n",
    "reserved-in-human": note(f"I document the {GENERATED_START} marker.\n"),
    "triple-begin": f"{GENERATED_START}\n{GENERATED_START}\n{GENERATED_START}\n{GENERATED_END}\n",
    "balanced-forged-pair": note(f"From {GENERATED_START} to {GENERATED_END}.\n"),
    "well-formed": note("human words\n"),
    "no-markers-at-all": "just prose\n",
    "human-only": f"{HUMAN_OPEN}\nwords\n{HUMAN_CLOSE}\n",
}

#: Fragments combined exhaustively, so the sweep covers orderings and counts the
#: named corpus does not enumerate by hand.
FRAGMENTS = [
    "",
    GENERATED_START + "\n",
    GENERATED_END + "\n",
    HUMAN_OPEN + "\n",
    HUMAN_CLOSE + "\n",
    "text\n",
]


def outcome(existing: str) -> tuple[str, str]:
    """(canonical, graph) outcome strings for one prior-note shape."""
    try:
        merge_protected_regions(existing=existing, rendered=FRESH, path="n.md")
        canonical = "ACCEPT"
    except ProtectedRegionError as exc:
        canonical = f"REFUSE:{exc}"
    try:
        graph_merge(existing=existing, rendered=FRESH, path="n.md")
        graph = "ACCEPT"
    except GraphProjectionError as exc:
        graph = f"REFUSE:{exc}"
    return canonical, graph


def main() -> int:
    shapes: list[tuple[str, str]] = list(NAMED.items())
    for n, combo in enumerate(itertools.product(FRAGMENTS, repeat=3)):
        shapes.append((f"sweep-{n}", "".join(combo)))

    agree = 0
    divergences: list[tuple[str, str, str]] = []
    refusals = 0
    for label, existing in shapes:
        canonical, graph = outcome(existing)
        if canonical.startswith("REFUSE"):
            refusals += 1
        if canonical == graph:
            agree += 1
        else:
            divergences.append((label, canonical, graph))

    print(f"  shapes compared        {len(shapes)}")
    print(f"  refused by canonical   {refusals}")
    print(f"  byte-identical outcome {agree}")
    print(f"  divergences            {len(divergences)}")
    for label, canonical, graph in divergences:
        print(f"    [{label}]\n      canonical: {canonical}\n      graph    : {graph}")

    # A run that compares nothing proves nothing: this lane has shipped controls
    # that passed by being no-ops more than once.
    assert len(shapes) > 200, len(shapes)
    assert refusals > 0, "no shape was refused -- the corpus is not exercising the guard"
    return 1 if divergences else 0


if __name__ == "__main__":
    raise SystemExit(main())
