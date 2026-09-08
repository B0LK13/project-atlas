"""A sealed backlog entry must not still say it is awaiting verification.

Two seals in this lane were blocked on the same defect: a `- [x]` entry whose
text declared it INTEGRATED and SEALED while its lifecycle parenthetical still
read "AWAITING IV -- merge NOT pre-authorized". Anything keying on the label --
a reader, an agent, a tool -- got the opposite of the truth.

It was found by review both times, fixed by hand both times, and reintroduced
the second time by writing a new seal from the template of the first. A sweep
was described in a commit message after the second occurrence; independent
verification pointed out that a described instrument is not an available one,
and that nothing prevented a third. This is that sweep, committed.
"""

from __future__ import annotations

import pathlib
import re

BACKLOG = pathlib.Path(__file__).resolve().parents[2] / "docs" / "backlog.md"

#: Lifecycle text that asserts work is not yet integrated.
PRE_MERGE = re.compile(rb"AWAITING IV|merge NOT pre-authorized", re.I)


def _checked_lines() -> list[tuple[int, bytes]]:
    raw = BACKLOG.read_bytes().split(b"\n")
    return [(n, line) for n, line in enumerate(raw, 1) if line.startswith(b"- [x] ")]


def test_no_sealed_entry_claims_it_is_awaiting_verification() -> None:
    offenders = [
        (n, line[:90].decode("utf-8", "replace"))
        for n, line in _checked_lines()
        if PRE_MERGE.search(line)
    ]
    assert not offenders, (
        "sealed backlog entries still carrying pre-merge lifecycle text: " f"{offenders}"
    )


def test_no_backlog_line_ends_in_a_double_period() -> None:
    """Sealing appends after stripping the terminal period; an off-by-one leaves `..`."""
    raw = BACKLOG.read_bytes().split(b"\n")
    offenders = [n for n, line in enumerate(raw, 1) if line.endswith(b"..")]
    assert not offenders, f"backlog lines ending in a double period: {offenders}"


def test_the_sweep_actually_looks_at_something() -> None:
    """Guard against the checks passing because they scanned nothing.

    Both tests above are satisfied by an empty file. This lane has twice shipped
    a negative control that passed because it was a no-op, so the sweep asserts
    it has a corpus before asserting anything about it.
    """
    assert BACKLOG.is_file(), BACKLOG
    assert len(_checked_lines()) > 100, len(_checked_lines())
