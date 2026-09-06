"""The CLI surface, observed on the parser argparse actually builds.

Six rounds of independent verification defeated six static answers to one
question: *which parser does the operator actually get?* Walk order, name
ownership, the call `main` makes, the module attribute, the entry point, and
finally the module-object write forms -- each fix closed a spelling and left
the class, because that question is a **runtime** property of a language where
any name can be rebound through an attribute, a subscript, `__dict__`,
`vars()`, `object.__setattr__`, or a computed `setattr`.

So these tests do not read `cli.py`. They import it, build the parser, and ask
the parser what it exposes. Every attack found across those six rounds --
seam shadowing in any spelling, parser rebinding, decoy factories, decorated
factories, module-attribute writes, control-flow evasion, a factory returning
an object it did not build, `dest` changes, deleted arguments -- changes what
this observes, by construction rather than by enumeration.

The static checks in `test_atlas3_demo_isolation_001.py` remain as
defence-in-depth against *deletions in a diff*. These are the ones that
establish what the CLI exposes.
"""

from __future__ import annotations

import argparse

import pytest

from project_atlas.atlas3.cli import ATLAS3_COMMANDS
from project_atlas.cli import build_parser

#: Certified top-level commands (CLAUDE.md's command list).
CERTIFIED_COMMANDS = ("connect", "ask2", "kdiff", "brief", "capture")

#: Documented flags per certified command, with the attribute each must land
#: on. `dest` is pinned deliberately: renaming it leaves the flag accepted and
#: silently drops its effect, which no "the option exists" check would catch.
CERTIFIED_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    # `brief --project` is repeatable, so its dest is plural. Pinned from the
    # built parser rather than assumed -- this test caught the assumption.
    "brief": (("--vault", "vault"), ("--project", "projects")),
    "ask2": (("--vault", "vault"), ("--project", "project"), ("--question", "question")),
    "kdiff": (("--vault", "vault"), ("--project", "project")),
    "connect": (("--vault", "vault"),),
}

#: Certified subcommands, whose whole operator interface lives one level down.
CERTIFIED_SUBCOMMAND_OPTIONS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    ("capture", "record"): (
        ("--vault", "vault"),
        ("--project", "project"),
        ("--summary", "summary"),
    ),
    ("capture", "list"): (("--vault", "vault"),),
}


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(actions) == 1, f"expected exactly one subparser group, found {len(actions)}"
    return actions[0]


def _commands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    return dict(_subparser_action(parser).choices)


def _options(parser: argparse.ArgumentParser) -> dict[str, str]:
    """option string -> dest, for every action on this parser."""
    return {
        option: action.dest
        for action in parser._actions
        for option in action.option_strings
    }


@pytest.fixture(scope="module")
def built() -> argparse.ArgumentParser:
    """The real parser, built the way the console script builds it."""
    return build_parser()


@pytest.mark.parametrize("command", CERTIFIED_COMMANDS)
def test_certified_command_is_exposed(command: str, built: argparse.ArgumentParser) -> None:
    """Not "cli.py contains a registration" -- the parser answers to it."""
    assert command in _commands(built), (
        f"certified command {command!r} is not exposed by the built parser"
    )


def test_atlas3_seam_actually_ran(built: argparse.ArgumentParser) -> None:
    """The seam's effect, not its syntax.

    Shadowing `register_atlas3_parsers`, rebinding it through the module
    object by any spelling, or skipping the call with an early `return` all
    leave the source looking correct and produce a parser with no Atlas 3
    commands. This sees the absence.
    """
    exposed = set(_commands(built))
    missing = sorted(set(ATLAS3_COMMANDS) - exposed)
    assert missing == [], f"Atlas 3 seam did not register: {missing}"


def test_no_certified_command_is_demoted(built: argparse.ArgumentParser) -> None:
    """Rebinding the top-level group re-routes registrations under another parser.

    Observed as the certified commands no longer being top-level, whatever
    spelling moved them.
    """
    top_level = set(_commands(built))
    for command in CERTIFIED_COMMANDS:
        assert command in top_level, f"{command!r} is no longer a top-level command"


@pytest.mark.parametrize("command", sorted(CERTIFIED_OPTIONS))
def test_certified_command_keeps_its_documented_options(
    command: str, built: argparse.ArgumentParser
) -> None:
    """Flag *and* `dest`: a renamed dest accepts the flag and drops its effect."""
    options = _options(_commands(built)[command])
    for flag, dest in CERTIFIED_OPTIONS[command]:
        assert flag in options, f"{command} no longer accepts {flag}"
        assert options[flag] == dest, (
            f"{command} {flag} now lands on {options[flag]!r}, not {dest!r}; "
            "the flag would be accepted and silently ignored"
        )


@pytest.mark.parametrize("pair", sorted(CERTIFIED_SUBCOMMAND_OPTIONS))
def test_certified_subcommand_keeps_its_documented_options(
    pair: tuple[str, str], built: argparse.ArgumentParser
) -> None:
    command, subcommand = pair
    parent = _commands(built)[command]
    children = _commands(parent)
    assert subcommand in children, f"{command} no longer exposes {subcommand!r}"
    options = _options(children[subcommand])
    for flag, dest in CERTIFIED_SUBCOMMAND_OPTIONS[pair]:
        assert flag in options, f"{command} {subcommand} no longer accepts {flag}"
        assert options[flag] == dest


def test_certified_commands_parse_a_documented_invocation(
    built: argparse.ArgumentParser,
) -> None:
    """End to end through argparse: the documented invocation still parses."""
    parsed = built.parse_args(["brief", "--vault", "/tmp/v", "--project", "p"])
    assert parsed.command == "brief"
    assert str(parsed.vault) == "/tmp/v"
    assert parsed.projects == ["p"]
