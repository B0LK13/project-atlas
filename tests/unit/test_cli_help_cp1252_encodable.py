"""F3: every help screen must survive a Windows cp1252 console.

`atlas --help` was fixed once (049d86e8) and the sweep was incomplete: four
SUBCOMMAND screens still raised UnicodeEncodeError, which on Windows is a crash
rather than a cosmetic defect. A per-command test cannot prevent that
recurring -- the next arrow lands in whichever screen has no test.

So this walks the parser tree and renders every screen. Adding a new
subcommand with a non-ASCII help string fails here automatically, without
anybody remembering to extend a list.

Why render instead of grepping the source: the mapping from a non-ASCII source
line to a failing screen is NOT one-to-one. argparse prints a subparser's
`help=` in its PARENT's screen, so the string at cli.py:2785 makes
`atlas openai-import --help` fail while `atlas openai-import parse --help` is
clean. A source grep would point at the wrong command.
"""

from __future__ import annotations

import argparse
import contextlib
import io

import pytest

from project_atlas.cli import build_parser

# The parser tree is large; a walk that silently found nothing would make every
# assertion below vacuously true, so the count itself is asserted.
MINIMUM_EXPECTED_SCREENS = 200


def _all_command_paths() -> list[list[str]]:
    parser = build_parser()
    paths: list[list[str]] = []

    def walk(node: argparse.ArgumentParser, prefix: list[str]) -> None:
        paths.append(prefix)
        for action in node._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    walk(sub, [*prefix, name])

    walk(parser, [])
    return paths


def _render(path: list[str]) -> str:
    parser = build_parser()
    buf = io.StringIO()
    with (
        contextlib.redirect_stdout(buf),
        contextlib.redirect_stderr(buf),
        contextlib.suppress(SystemExit),
    ):
        parser.parse_args([*path, "--help"])
    return buf.getvalue()


def test_the_walk_actually_finds_the_command_tree() -> None:
    """Without this, a broken walk would make the sweep below pass on nothing."""
    paths = _all_command_paths()
    assert len(paths) >= MINIMUM_EXPECTED_SCREENS, (
        f"only {len(paths)} help screens discovered; the parser walk is broken, "
        "so the cp1252 sweep would be vacuous"
    )


def test_every_help_screen_is_cp1252_encodable() -> None:
    """A Windows console using cp1252 must be able to print every screen."""
    failures: list[str] = []
    for path in _all_command_paths():
        text = _render(path)
        try:
            text.encode("cp1252")
        except UnicodeEncodeError as exc:
            bad = text[exc.start : exc.end]
            command = " ".join(["atlas", *path]).strip()
            failures.append(f"{command!r} contains {bad!r} (U+{ord(bad[0]):04X})")

    assert not failures, "help screens that a cp1252 console cannot print:\n  " + "\n  ".join(
        failures
    )


@pytest.mark.parametrize(
    "path",
    [
        ["runtime", "hybrid-retrieve"],
        ["twin-fixture", "build"],
        ["openai-import"],
        ["work-readiness", "handoff"],
    ],
    ids=[
        "runtime-hybrid-retrieve",
        "twin-fixture-build",
        "openai-import",
        "work-readiness-handoff",
    ],
)
def test_the_four_screens_that_actually_regressed(path: list[str]) -> None:
    """Named explicitly so a regression names the command, not just a count."""
    _render(path).encode("cp1252")
