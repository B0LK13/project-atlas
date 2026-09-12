"""AS-OBSIDIAN-CAPTURE-001 F13 -- named ``tests/unit/*.py`` paths must exist.

F5's sealed WORKLOG entry abbreviated a suite list. Two of those
abbreviations expand to filenames that do not exist. The same class was
corrected in F6, F8 and F9; F5's copy was left because it sits in the
byte-identical prefix later seals rely on. This package is the allowed
edit of that one paragraph, plus a sweep so the next abbreviation cannot
rot the same way.

Scope of the sweep: every ``tests/unit/<name>.py`` path written in
``WORKLOG.md`` and ``docs/evidence/*.md`` must exist. Stems mentioned
without that path form are out of scope -- that is how this package can
name the two false expansions without failing its own guard.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKLOG = ROOT / "WORKLOG.md"
EVIDENCE = ROOT / "docs" / "evidence"
UNIT = ROOT / "tests" / "unit"

NAMED_UNIT = re.compile(r"tests/unit/[A-Za-z0-9_.-]+\.py")

#: The two stems F5's abbreviation invented. They must not appear as
#: ``tests/unit/*.py`` paths anywhere the sweep looks, or the guard would
#: either fail closed on a documented absence or need an exception list.
FALSE_EXPANSIONS = (
    "test_as_graph_005_projections_adversarial.py",
    "test_as_coder_alpha_obsidian_001_r1_001.py",
)

#: Pre-existing named unit paths that do not exist, outside the F5
#: paragraph this package may edit. ``test_dogfood_001_source_marker_identity_write.py``
#: was moved to ``tests/integration/``; earlier WORKLOG lines still cite
#: the unit path. Rewriting those lines would edit a different historical
#: record. The set is the whole residual: a new miss must fail, and if
#: the file returns to ``tests/unit/`` the residual is stale.
HISTORICAL_MISSING = frozenset(
    {
        "tests/unit/test_dogfood_001_source_marker_identity_write.py",
    }
)


def _named_paths(text: str) -> set[str]:
    return set(NAMED_UNIT.findall(text))


def _corpus() -> list[tuple[pathlib.Path, str]]:
    files = [(WORKLOG, WORKLOG.read_text(encoding="utf-8"))]
    for path in sorted(EVIDENCE.glob("*.md")):
        files.append((path, path.read_text(encoding="utf-8")))
    return files


def _missing_named_unit_paths(texts: list[str]) -> list[str]:
    missing: list[str] = []
    for text in texts:
        for rel in sorted(_named_paths(text)):
            if not (ROOT / rel).is_file():
                missing.append(rel)
    return missing


def test_f13_every_named_unit_path_exists() -> None:
    texts = [text for _path, text in _corpus()]
    seen = {rel for text in texts for rel in _named_paths(text)}
    missing = set(_missing_named_unit_paths(texts))
    unexpected = sorted(missing - HISTORICAL_MISSING)
    stale = sorted(HISTORICAL_MISSING - missing)
    assert unexpected == [], f"new missing named unit paths: {unexpected}"
    assert stale == [], f"historical residual now exists; drop it: {stale}"
    assert len(seen) >= 8, f"sweep scanned too little: {len(seen)}"


def test_f13_the_eight_f5_paths_are_named_and_present() -> None:
    """The correction writes the eight real paths; each must be named and exist."""
    required = (
        "tests/unit/test_as_obsidian_capture_001.py",
        "tests/unit/test_as_obsidian_capture_001_f3.py",
        "tests/unit/test_as_obsidian_capture_001_f5_newline_fidelity.py",
        "tests/unit/test_as_graph_005_projections.py",
        "tests/unit/test_as_graph_005_adversarial.py",
        "tests/unit/test_as_graph_005_f4_canonical_semantics.py",
        "tests/unit/test_as_coder_alpha_obsidian_001.py",
        "tests/unit/test_as_coder_alpha_obsidian_r1_001.py",
    )
    text = WORKLOG.read_text(encoding="utf-8")
    named = _named_paths(text)
    absent = [rel for rel in required if rel not in named]
    assert absent == [], f"F5 correction omitted: {absent}"
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    assert missing == [], missing


def test_f13_false_expansions_are_not_written_as_unit_paths() -> None:
    """Naming the absent files as ``tests/unit/*.py`` would fail the sweep.

    They are documented as stems so the correction stays honest and the
    guard stays exception-free.
    """
    for _path, text in _corpus():
        named = _named_paths(text)
        leaked = [name for name in FALSE_EXPANSIONS if f"tests/unit/{name}" in named]
        assert leaked == [], leaked


def test_f13_the_sweep_fails_when_a_named_path_is_missing() -> None:
    """Negative control: a ``tests/unit/*.py`` path that does not exist is a miss."""
    fake = "tests/unit/test_f13_does_not_exist.py"
    assert not (ROOT / fake).is_file()
    assert _missing_named_unit_paths([f"see `{fake}`"]) == [fake]


def test_f13_the_historical_residual_is_still_absent_from_unit() -> None:
    """The residual is a moved file, not a hole we chose to ignore forever."""
    assert HISTORICAL_MISSING
    for rel in HISTORICAL_MISSING:
        assert not (ROOT / rel).is_file(), rel
    successor = ROOT / "tests/integration/test_dogfood_001_source_marker_identity_write.py"
    assert successor.is_file(), successor


def test_f13_issue_755_ninth_path_was_not_in_the_abbreviation() -> None:
    """#755 listed F6 as a ninth path. F6 is a later package, not F5's suite.

    Inserting it into the sealed F5 paragraph would invent a file the
    original abbreviation did not name. The F6 module exists; it is simply
    not part of this correction's written-out list.
    """
    f6 = "tests/unit/test_as_obsidian_capture_001_f6_error_boundary.py"
    assert (ROOT / f6).is_file()
    # The F5 correction block must not claim F6 as one of the eight.
    # Locate the F13 CORRECTION marker and the next figure line.
    text = WORKLOG.read_text(encoding="utf-8")
    start = text.find("**F13 CORRECTION (issue #755)")
    assert start != -1
    end = text.find("= 264 passed, 4 xfailed", start)
    assert end != -1
    block = text[start:end]
    assert f6 not in block
