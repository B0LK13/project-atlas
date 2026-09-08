"""A sealed record must not still say it is awaiting verification.

Three seal commits in this lane shipped a `- [x]` backlog entry whose text
declared it INTEGRATED and SEALED while its lifecycle parenthetical still read
"AWAITING IV -- merge NOT pre-authorized": `aa59ac79` (the F6 *and* F7 lines),
`b7c1ed41` (F7) and `fd7cf24b` (F8). Anything keying on the label -- a reader,
an agent, a tool -- got the opposite of the truth.

It was found by review each time and fixed by hand each time, and reintroduced
by writing a new seal from the template of the previous one. A sweep was
described in a commit message after the second occurrence; verification pointed
out that a described instrument is not an available one. This is that sweep,
committed.

Scope. Two of the three historical occurrences of this defect class lived in
evidence-receipt Status headers rather than the backlog, so the receipts are
swept too. The phrase set is deliberately broader than the attested wording:
`awaiting independent verification` is included because that is the exact
phrase the F6 and F7 receipts used for this same defect, and both British and
American spellings of "pre-authorised" are matched.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs" / "backlog.md"
EVIDENCE = ROOT / "docs" / "evidence"

#: A completed checkbox, however it is bulleted, indented or capitalised.
DONE = re.compile(rb"^\s*[-*] \[[xX]\] ")

#: Text asserting the work is NOT yet integrated.
PRE_MERGE = re.compile(
    rb"AWAITING\s+(IV|INDEPENDENT\s+VERIFICATION)"
    rb"|awaiting\s+independent\s+verification"
    rb"|merge\s+NOT\s+pre-authori[sz]ed"
    rb"|PENDING\s+IV"
    rb"|NOT\s+YET\s+(VERIFIED|SEALED)"
    rb"|\*\*Not\s+sealed\.\*\*",
    re.I,
)


def _done_lines() -> list[tuple[str, int, bytes]]:
    out = []
    for line_no, line in enumerate(BACKLOG.read_bytes().split(b"\n"), 1):
        if DONE.match(line):
            out.append((BACKLOG.name, line_no, line))
    return out


#: A quoted span. A sealed header may legitimately QUOTE the wording it retracts
#: -- F6's and F7's both do -- and a quotation is not a live claim. Every sweep in
#: this lane has had to learn this distinction; it is cheaper to encode it.
#: ``\u`` escapes are invalid in a bytes pattern, so the curly quotes are their
#: literal UTF-8 encodings.
_Q = rb'["\xe2\x80\x9c\xe2\x80\x9d]'
QUOTED = re.compile(_Q + rb"(?:(?!" + _Q + rb").)*" + _Q, re.S)


def _live_text(line: bytes) -> bytes:
    """The line with quoted spans removed, so retractions do not read as claims."""
    return QUOTED.sub(b" ", line)


def _sealed_receipts() -> list[tuple[str, int, bytes]]:
    """Status headers in receipts that declare themselves SEALED."""
    out = []
    for path in sorted(EVIDENCE.glob("*.md")):
        for line_no, line in enumerate(path.read_bytes().split(b"\n"), 1):
            if line.startswith(b"**Status:**") and b"SEALED" in line:
                out.append((path.name, line_no, line))
    return out


def test_no_sealed_entry_claims_it_is_awaiting_verification() -> None:
    offenders = [
        (name, n, line[:90].decode("utf-8", "replace"))
        for name, n, line in _done_lines() + _sealed_receipts()
        if PRE_MERGE.search(_live_text(line))
    ]
    assert not offenders, f"sealed records still carrying pre-merge lifecycle text: {offenders}"


def test_no_backlog_line_ends_in_a_double_period() -> None:
    """Sealing appends after stripping the terminal period; off-by-one leaves `..`.

    An ellipsis is not that defect, and `WORKLOG.md` already contains one, so a
    naive ``endswith("..")`` would redden CI on an unrelated prose edit.
    """
    offenders = [
        n
        for n, line in enumerate(BACKLOG.read_bytes().split(b"\n"), 1)
        if line.endswith(b"..") and not line.endswith(b"...")
    ]
    assert not offenders, f"backlog lines ending in a double period: {offenders}"


def test_the_sweep_actually_looks_at_something() -> None:
    """Guard against the checks passing because they scanned nothing.

    Both checks above are satisfied by an empty file. This lane has twice
    shipped a negative control that passed by being a no-op, so the sweep
    asserts it has a corpus before asserting anything about it.
    """
    assert BACKLOG.is_file(), BACKLOG
    assert len(_done_lines()) > 100, len(_done_lines())
    assert len(_sealed_receipts()) >= 2, len(_sealed_receipts())
