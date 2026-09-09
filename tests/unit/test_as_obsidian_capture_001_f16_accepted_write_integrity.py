"""AS-OBSIDIAN-CAPTURE-001-F16 — human bytes across writes that SUCCEED.

Every protected-region test in this repository pins a **refusal**: duplicate
names, unpaired markers, containment, malformed generated spans. Refusals are the
safe direction. The dangerous case is the opposite one -- a write that succeeds
while quietly altering bytes the operator owns -- because by construction every
marker, count and placement check has already passed on it.

Measured on `b87b4a22`, mechanically rather than by reading: **eight** assertions
across two modules touch extracted human regions, and **all eight compare an
extraction against a literal**. Zero compare an extraction against another
extraction. So nothing asserted the invariant itself:

    the human regions that come out are the human regions that went in

That is what this module asserts, over a corpus, on the success path, for every
generated-span-preserving writer reachable without an owner-gated exception.

**A clean zero is worthless unless it can fail**, and this lane has shipped
sweeps whose zero was structural. So the falsification is not described here, it
is *executed*: the same corpus is re-run through writers deliberately corrupted
in the two ways this module exists to catch -- a single byte dropped from each
human body, and CRLF normalised to LF -- and those runs must report changes. If
the detector ever stops seeing corruption, the tests that assert zero stop
meaning anything, and the control tests fail first.

**Not covered, and why.** `ingestion._generated_content` is the fourth
generated-span-preserving writer and it is *known* to rewrite operator CRLF
(AS-OBSIDIAN-CAPTURE-001-F15, issue #759). It is excluded here because
`src/project_atlas/ingestion.py` sits on the frozen surface enumerated by
`tests/unit/test_atlas3_demo_isolation_001.py`, and adding it would either fail
this suite for a defect this package does not own or require an owner-approved
sha256-pinned exception under `docs/atlas-3/ARCHITECTURE.md` §9.1, which this
lane cannot self-grant. The exclusion is asserted below so it stays a decision
rather than becoming an accident.
"""

from __future__ import annotations

import ast
import itertools
from collections.abc import Callable
from pathlib import Path

import project_atlas.graph_projections as gp
import project_atlas.obsidian_capture_note as ocn
import project_atlas.obsidian_projection as op
from project_atlas.graph_projections import GraphProjectionError
from project_atlas.protected_regions import (
    ProtectedRegionError,
    extract_human_regions,
    merge_protected_regions,
)

GENERATED_START = "<!-- atlas:generated:start -->"
GENERATED_END = "<!-- atlas:generated:end -->"

# ruff: noqa: RUF001
# RUF001 is suppressed for this module: the corpus below deliberately contains
# a NO-BREAK SPACE and a ZERO WIDTH SPACE. They are exactly the codepoints a
# normalising writer would silently replace or drop, so flagging them as
# "ambiguous" is correct in prose and wrong here -- the ambiguity is the test.

#: Bodies chosen so that a corruption of either class has something to destroy:
#: trailing and leading runs, CRLF, tabs, blank lines, zero-width and non-ASCII
#: codepoints, marker-shaped text, and a body long enough that a truncation is
#: not masked by a short string.
BODIES = (
    "plain",
    "with\ttab",
    "trailing   ",
    "   leading",
    "uni üñïçø∂é",
    "a\r\nb",
    "",
    "  ",
    "<!-- BEGIN HUMAN: inner -->",
    "<!-- END HUMAN: x -->",
    GENERATED_START,
    "zero​width",
    "nbsp here",
    "emoji 🧪",
    "back\\slash",
    "l1\nl2\nl3",
    "\n\n",
    "-- dashes --",
    "tab\tand\ttabs",
    "x" * 300,
)

NAMES = ("notes", "Notes", "n o t e s", "a-b", "a_b", "α", "x")


def _region(name: str, body: str) -> str:
    return f"<!-- BEGIN HUMAN: {name} -->\n{body}\n<!-- END HUMAN: {name} -->"


def _pairs() -> list[tuple[str, str, str]]:
    """(label, prior, rendered) for every accepted-write candidate."""
    out: list[tuple[str, str, str]] = []
    for body, name in itertools.product(BODIES, NAMES):
        prior = f"{GENERATED_START}\nold\n{GENERATED_END}\n" + _region(name, body) + "\n"
        fresh = (
            f"{GENERATED_START}\nnew\n{GENERATED_END}\n"
            + _region(name, "PLACEHOLDER")
            + "\n"
        )
        out.append((f"{name!r}/{body!r}"[:60], prior, fresh))
    for first, second in itertools.product(BODIES[:8], repeat=2):
        prior = (
            f"{GENERATED_START}\ng\n{GENERATED_END}\n"
            + _region("alpha", first)
            + "\n"
            + _region("beta", second)
            + "\n"
        )
        # The render lists them in the OPPOSITE order, and drops nothing.
        fresh = (
            f"{GENERATED_START}\ng2\n{GENERATED_END}\n"
            + _region("beta", "PH")
            + "\n"
            + _region("alpha", "PH")
            + "\n"
        )
        out.append((f"reordered {first!r}/{second!r}"[:60], prior, fresh))
    return out


def _safe_extract(text: str) -> dict[tuple[str, ...], str] | None:
    try:
        return extract_human_regions(text)
    except (ProtectedRegionError, ValueError):
        return None


Merger = Callable[..., str]

#: Every generated-span-preserving merge reachable without an owner-gated
#: exception. `ingestion._generated_content` is deliberately absent -- see the
#: module docstring, and `test_f16_the_frozen_writer_is_excluded_on_purpose`.
MERGERS: dict[str, tuple[Merger, type[Exception]]] = {
    "protected_regions.merge_protected_regions": (
        merge_protected_regions,
        ProtectedRegionError,
    ),
    "graph_projections._merge_protected_regions": (
        gp._merge_protected_regions,
        GraphProjectionError,
    ),
}


class Report:
    """Outcome counts for one sweep, plus the cases whose human bytes moved."""

    def __init__(self) -> None:
        self.accepted = 0
        self.refused = 0
        self.changed: list[str] = []

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"<accepted={self.accepted} refused={self.refused} "
            f"changed={len(self.changed)}>"
        )


def _sweep(corrupt: Callable[[str], str] | None = None) -> Report:
    """Run every pair through every merger; report where human bytes moved.

    ``corrupt`` wraps the merged output, standing in for a writer that succeeds
    while altering the operator's bytes. It is how the zero this module asserts
    is falsified -- in the same test run, not in a session transcript.
    """
    report = Report()
    for label, prior, fresh in _pairs():
        before = _safe_extract(prior)
        if not before:
            continue
        for name, (merge, error) in MERGERS.items():
            try:
                merged = merge(existing=prior, rendered=fresh, path="n.md")
            except (error, ValueError):
                report.refused += 1
                continue
            report.accepted += 1
            if corrupt is not None:
                merged = corrupt(merged)
            after = _safe_extract(merged)
            if after != before:
                report.changed.append(f"{name}: {label}")
    return report


def _drop_one_byte(text: str) -> str:
    """Lose the last character of every human body -- individual-byte loss."""
    out: list[str] = []
    for chunk in text.split("<!-- END HUMAN"):
        marker = "-->\n"
        idx = chunk.rfind(marker)
        kept = chunk[: idx + len(marker)] + chunk[idx + len(marker) : -1]
        out.append(kept if idx >= 0 else chunk)
    return "<!-- END HUMAN".join(out)


def _normalise_newlines(text: str) -> str:
    """Rewrite CRLF to LF -- the corruption `read_note_text` exists to prevent."""
    return text.replace("\r\n", "\n")


#: Floors, not exact counts. They exist so an inert or truncated corpus cannot
#: pass by scanning nothing -- the failure this lane has shipped twice -- while
#: leaving room for the corpus to grow. The measured values at `b87b4a22` are
#: 332 accepted and 12 refused.
MIN_ACCEPTED = 300
MIN_REFUSED = 1


def test_f16_human_bytes_survive_every_accepted_merge() -> None:
    """The invariant: what comes out is what went in, byte for byte.

    Compared as extracted regions rather than as a slice of the document,
    because the newline *after* ``<!-- END HUMAN: … -->`` belongs to the
    surrounding generated structure and legitimately comes from the fresh
    render. A hand-written slice that includes it fails for a reason unrelated
    to the defect -- which is exactly how an earlier probe of mine made three
    correct writers look broken.
    """
    report = _sweep()
    assert not report.changed, (
        f"{len(report.changed)} accepted writes altered operator bytes: "
        f"{report.changed[:5]}"
    )
    assert report.accepted >= MIN_ACCEPTED, f"corpus shrank: {report!r}"
    assert report.refused >= MIN_REFUSED, (
        f"no shape in the corpus is refused any more, so it no longer reaches "
        f"the accept/refuse boundary and a zero here proves less than it looks: {report!r}"
    )


def test_f16_the_zero_is_falsifiable_by_individual_byte_loss() -> None:
    """Control: a writer that loses one byte per human body must be caught.

    Without this, `test_f16_human_bytes_survive_every_accepted_merge` cannot be
    distinguished from a sweep that compares nothing.
    """
    report = _sweep(_drop_one_byte)
    assert len(report.changed) == report.accepted, (
        "a one-byte loss in every human body must be detected in every accepted "
        f"write, not some: {report!r}"
    )


def test_f16_the_zero_is_falsifiable_by_newline_normalisation() -> None:
    """Control: CRLF rewritten to LF must be caught.

    This is the corruption `protected_regions.read_note_text` exists to prevent
    and the one `ingestion._generated_content` still commits (#759), so it is the
    class most worth being able to see.

    Detected in fewer cases than the byte-loss control by construction -- only
    bodies that actually carry CRLF can register it -- which doubles as a check
    that the corpus contains such bodies at all.
    """
    report = _sweep(_normalise_newlines)
    assert report.changed, f"CRLF normalisation went undetected: {report!r}"
    assert len(report.changed) < report.accepted, (
        "every accepted write registered a newline change, which means the "
        "control is corrupting something other than CRLF-bearing bodies"
    )


def test_f16_human_bytes_survive_the_round_trip_to_disk(tmp_path: Path) -> None:
    """The success path end to end: merge, write, read back from disk.

    The merge is where the splice happens, but the operator's bytes are only
    safe if they are still intact in the file. Both atomic writers are exercised
    because a defect in either would be invisible to a merge-layer sweep.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    checked = 0
    for index, (label, prior, fresh) in enumerate(_pairs()):
        before = _safe_extract(prior)
        if not before:
            continue
        try:
            merged = merge_protected_regions(existing=prior, rendered=fresh, path="n.md")
        except (ProtectedRegionError, ValueError):
            continue
        payload = merged.encode("utf-8")

        graph_note = vault / f"g{index}.md"
        graph_note.write_bytes(prior.encode("utf-8"))
        gp._promote({graph_note: payload})
        assert _safe_extract(graph_note.read_bytes().decode("utf-8")) == before, label

        obsidian_note = vault / f"o{index}.md"
        obsidian_note.write_bytes(prior.encode("utf-8"))
        op._write_atomic(obsidian_note, payload, vault=vault)
        assert _safe_extract(obsidian_note.read_bytes().decode("utf-8")) == before, label

        # The third path. `obsidian_capture_note` does not reuse either writer
        # above -- it has its own `_write_atomic` delegating to
        # `capture_io.write_atomic_under_root`. An earlier revision of this
        # module swept two writers and claimed the disk round trip, which was a
        # coverage claim broader than the code behind it.
        capture_note = vault / f"c{index}.md"
        capture_note.write_bytes(prior.encode("utf-8"))
        ocn._write_atomic(capture_note, payload, root=vault)
        assert _safe_extract(capture_note.read_bytes().decode("utf-8")) == before, label
        checked += 1
    assert checked >= MIN_ACCEPTED // len(MERGERS), f"round trip covered only {checked}"


def test_f16_the_corpus_can_actually_carry_the_corruption_it_looks_for() -> None:
    """A corpus of well-behaved bodies would pass every assertion above vacuously.

    Asserted on the corpus rather than on the sweep, so it fails loudly if a
    future edit trims the interesting bodies out.
    """
    joined = "".join(BODIES)
    assert "\r\n" in joined, "no CRLF body: the newline control cannot bite"
    assert any(b != b.strip() and b.strip() for b in BODIES), "no leading/trailing runs"
    assert any(b == "" for b in BODIES), "no empty body"
    assert any(len(b) > 200 for b in BODIES), "no body long enough to hide a truncation"
    assert any("<!-- " in b for b in BODIES), "no marker-shaped body"
    assert any(not b.isascii() for b in BODIES), "no non-ASCII body"


def test_f16_the_frozen_writer_is_excluded_on_purpose() -> None:
    """`ingestion` is the fourth writer and is deliberately not swept.

    It rewrites operator CRLF (#759) and lives on the frozen surface, so
    including it would fail this suite for a defect this package does not own
    and cannot fix without an owner-approved exception. Asserted so the
    exclusion stays a decision: if the freeze is lifted and the defect fixed,
    this test is what tells the next maintainer to add it here.
    """
    assert not any("ingestion" in name for name in MERGERS), (
        "ingestion joined the sweep; it must not until #759 is fixed under an "
        "owner-approved §9.1 exception, or this suite will fail for a defect it "
        "does not own"
    )
    from project_atlas.ingestion import _generated_content

    assert callable(_generated_content), (
        "the excluded writer no longer exists under that name; the exclusion "
        "note and #759 both need revisiting"
    )


#: Modules that may splice human regions into a prior note, and how each is
#: covered here. Derived mechanically by :func:`_splicing_modules` at test time
#: rather than maintained by hand, so a NEW writer cannot be added without this
#: file being updated -- which is the point: the failure mode this package
#: guards against should be hard to introduce, not merely visible afterwards.
#: ``protected_regions.py`` is deliberately absent: it DEFINES the merge, it does
#: not splice into a prior note, so it is the implementation rather than a
#: writer. The structural test below caught it on its first run when an earlier
#: revision of this dict listed it -- which is the guard working, on its author.
WRITER_COVERAGE = {
    "src/project_atlas/graph_projections.py": "merge swept via MERGERS; disk via _promote",
    "src/project_atlas/obsidian_projection.py": (
        "shares the canonical merge; disk via _write_atomic"
    ),
    "src/project_atlas/obsidian_capture_note.py": (
        "shares the canonical merge (aliased import); disk via its own "
        "_write_atomic -> capture_io.write_atomic_under_root"
    ),
    "src/project_atlas/ingestion.py": (
        "EXCLUDED: frozen surface, and a known CRLF defect (#759). Adding it "
        "fails this suite for a defect this package does not own; see "
        "test_f16_the_frozen_writer_is_excluded_on_purpose"
    ),
}


def _splicing_modules() -> dict[str, list[str]]:
    """Every module that can splice human regions into a prior note.

    Derived from the source tree, not from a hand-kept list: any module that
    imports or calls ``merge_protected_regions``, ``read_note_text`` or
    ``_generated_content``. Those three are the only ways to obtain a prior
    note's human content in order to write it back.
    """
    splicers = {"merge_protected_regions", "read_note_text", "_generated_content"}
    found: dict[str, list[str]] = {}
    root = Path(__file__).resolve().parents[2] / "src" / "project_atlas"
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(errors="replace")
        if not any(name in source for name in splicers):
            continue
        names: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                "protected_regions"
            ):
                names |= {a.asname or a.name for a in node.names if a.name in splicers}
            elif isinstance(node, ast.Call):
                names |= {ast.unparse(node.func).split(".")[-1]} & splicers
        if names:
            rel = path.relative_to(root.parents[1]).as_posix()
            found[rel] = sorted(names)
    return found


def test_f16_every_splicing_writer_is_covered_or_explicitly_excluded() -> None:
    """Structural: a NEW writer cannot appear without this file being updated.

    The other tests here detect corruption in the writers they happen to sweep.
    This one makes an *uncovered writer* fail, which is the difference between
    "we test some writers" and "the set of writers is a closed, reviewed set".

    Derived rather than declared. If someone adds a fifth module that reads a
    prior note's human content in order to write it back, this fails until they
    either add it to the sweep or record why it is excluded -- and the recorded
    reason is what a reviewer reads.
    """
    discovered = _splicing_modules()
    assert discovered, "the derivation found nothing; it is no longer looking correctly"

    uncovered = sorted(set(discovered) - set(WRITER_COVERAGE))
    assert not uncovered, (
        f"module(s) can splice human regions but are not covered here: {uncovered}. "
        "Add them to the sweep, or record why they are excluded in WRITER_COVERAGE."
    )

    stale = sorted(set(WRITER_COVERAGE) - set(discovered))
    assert not stale, (
        f"WRITER_COVERAGE names module(s) that no longer splice: {stale}. "
        "A coverage claim outliving its subject is how this record rots."
    )

    # Renaming on import must not hide a writer. All three non-frozen writers
    # alias the canonical merge (`_merge_protected_regions`,
    # `_canonical_merge_protected_regions`), so a derivation that matched only
    # the original name would silently miss every one of them.
    aliased = {
        module
        for module, names in discovered.items()
        if any(name not in {"read_note_text", "_generated_content"} for name in names)
    }
    assert aliased, (
        "no module resolved an aliased merge import; the derivation has stopped "
        "following `from ... import merge_protected_regions as _x` and would now "
        "miss a writer that renames it"
    )
