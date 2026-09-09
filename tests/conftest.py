"""Session-wide human-content integrity enforcement (AS-OBSIDIAN-CAPTURE-001-F18).

Installs the boundary for the whole test session, so the property under test is
not "the writers we know about preserve operator bytes" but:

    every write to a note that already carried operator regions is observed, and
    any that altered those regions is reported with the primitive and the stack
    that produced it.

It REPORTS rather than fails, and that is a deliberate, measured decision rather
than timidity. An earlier revision failed the session on writes whose innermost
frame was in `src/project_atlas`, on the theory that this separated "Atlas
clobbered it" from "a test seeded its own content". Measurement killed that: a
caller handing already-damaged bytes to `capture_io` and a caller writing the
same bytes directly are the same act with different plumbing, and the innermost
frame names whichever helper landed the bytes rather than whoever authored the
damage. At the OS interface those two are indistinguishable, so the boundary
detects damage but cannot attribute responsibility.

Making it a gate therefore requires each legitimate operator-authoring site in
the suite to declare itself through `boundary.authorized(reason)`. That is a
real, bounded cost -- the census below -- and it belongs to whoever owns those
tests, not to this package.

**Opt-in, and that is a measured decision.** Enabling it for every session broke
three tests that spawn a nested `pytest`: the child process loads this conftest
too, and the added option changed its exit status. The sensor is not at fault and
the census below is real, but a monitor that changes the result of the suite it
observes is not an observer. Enable with `--human-content-boundary`; the census
it produces is reproducible on demand rather than continuously.

Making it continuous requires the nested-pytest interaction to be fixed first,
and that belongs to whoever owns those tests -- it is recorded here rather than
worked around.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent / "unit"))

from human_content_boundary import HumanContentBoundary  # type: ignore[import-not-found]

_BOUNDARY = HumanContentBoundary()


def pytest_addoption(parser: Any) -> None:
    parser.addoption(
        "--human-content-boundary",
        action="store_true",
        help=(
            "install the AS-OBSIDIAN-CAPTURE-001-F18 human-content write boundary "
            "for the session and report every write that altered operator regions"
        ),
    )


def pytest_configure(config: Any) -> None:
    if config.getoption("--human-content-boundary"):
        _BOUNDARY.install()


def pytest_terminal_summary(terminalreporter: Any, *a: Any, **k: Any) -> None:
    if not _BOUNDARY._saved:
        return
    _BOUNDARY.uninstall()
    terminalreporter.write_line("")
    terminalreporter.write_line(
        f"human-content boundary: {_BOUNDARY.checked} protected write(s) checked, "
        f"{len(_BOUNDARY.violations)} altered operator regions "
        "(reported, not gated -- see tests/conftest.py for why)"
    )
    for violation in _BOUNDARY.violations[:5]:
        terminalreporter.write_line(f"  {violation.primitive} -> {violation.path}")

    # F19. The census is reported per attribution state rather than as a single
    # total, because "how many writes happened" and "how many we can explain"
    # are different questions and only the second one is governance.
    counts = _BOUNDARY.ledger.by_state()
    terminalreporter.write_line(
        "attribution: " + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        or "attribution: (no protected writes observed)"
    )
    total = sum(counts.values())
    attributed = counts["GOVERNED_AND_ATTRIBUTED"] + counts["ATTRIBUTED_BUT_UNAUTHORIZED"]
    if total:
        terminalreporter.write_line(
            f"  {attributed}/{total} protected writes carry a trusted execution identity "
            f"({attributed * 100 // total}%)"
        )
