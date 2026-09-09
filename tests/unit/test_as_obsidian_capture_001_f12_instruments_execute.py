"""AS-OBSIDIAN-CAPTURE-001-F12 — the committed instruments must actually run.

Three evidence instruments live under ``docs/scripts/``. Each was committed for
the same stated reason: an instrument *described* is not an instrument
*available*, and a seal that cites measurements no clean checkout can reproduce
is citing nothing.

Measured on `a7adce4e`: **none of the three is referenced by any test or CI
file.** `pyproject.toml` sets ``testpaths = ["tests"]``, so pytest never sees
them and `ruff check .` does not lint them either. They can be renamed, broken
by a refactor, or silently invalidated, and nothing notices — which is the same
failure the seals were meant to close, one level up.

This wires them, with deliberately different scope per instrument, because they
do not have the same contract:

* ``f9_diagnostic_parity.py`` has a clean pass/fail contract and touches
  nothing. It is **executed**, and its result asserted.
* ``f8_near_miss_controls.py`` deliberately MUTATES source files and restores
  them. Running that inside CI would leave a broken tree if it were interrupted,
  so it is **not executed here** — only checked to import cleanly and still
  expose the entry point the evidence cites. Rot is caught; destruction is not
  risked.
* ``seal_retracted_claim_sweep.py`` over-reports by design and needs a human to
  classify its hits, so a pass/fail assertion on its exit code would be wrong.
  It too is **import- and interface-checked** only.

What this does NOT do, stated so nobody reads more into a green suite: it does
not verify the instruments are *correct*, only that they still load and, for the
one with a decidable contract, still report what the record says.

And one concrete limit of the instrument it does execute, worth naming here
because a green line is otherwise reassuring beyond its warrant:
``f9_diagnostic_parity.py`` always passes ``rendered=FRESH``. It varies only the
prior note, so it **cannot observe a rendered-side divergence at all** -- which
is exactly the class F10 had to find with a two-sided sweep. Wiring this up
catches rot and message-parity regressions; it does not make the parity claim
broader than the corpus behind it.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import types

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "docs" / "scripts"

#: Instruments cited by sealed evidence records, with the callable each record
#: names. A rename or a broken import fails here rather than silently rotting.
CITED = {
    "f9_diagnostic_parity.py": ("main", "outcome", "NAMED", "FRAGMENTS"),
    "f8_near_miss_controls.py": ("main", "CONTROLS", "ANCHOR"),
    "seal_retracted_claim_sweep.py": ("sweep", "CLAIMS", "RETRACTION"),
}


def _load(name: str) -> types.ModuleType:
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", sorted(CITED))
def test_f12_every_cited_instrument_still_exists(name: str) -> None:
    assert (SCRIPTS / name).is_file(), f"{name} is cited by a sealed record and is missing"


@pytest.mark.parametrize("name", sorted(CITED))
def test_f12_every_cited_instrument_imports_cleanly(name: str) -> None:
    """A broken import is how an uncited, unlinted script rots."""
    _load(name)


@pytest.mark.parametrize("name", sorted(CITED))
def test_f12_every_cited_instrument_keeps_the_interface_its_record_names(name: str) -> None:
    module = _load(name)
    missing = [attr for attr in CITED[name] if not hasattr(module, attr)]
    assert not missing, f"{name} lost {missing}, which its evidence record refers to"


def test_f12_the_parity_instrument_still_reports_what_the_seal_claims() -> None:
    """The one instrument with a decidable contract is actually executed.

    F9's seal cites this script's result. If the two writers ever diverge again,
    or the corpus goes inert, this fails in CI rather than the next time someone
    happens to run it by hand.
    """
    module = _load("f9_diagnostic_parity.py")
    exit_code = module.main()
    assert exit_code == 0, "the two writers diverged, or the corpus stopped exercising them"


def test_f12_the_parity_instrument_runs_as_a_script_too() -> None:
    """Cited as a command in the seal, so the command form is what is checked."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "f9_diagnostic_parity.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "divergences            0" in result.stdout, result.stdout


def test_f12_the_mutating_instrument_is_not_executed_by_this_suite() -> None:
    """Guard the deliberate scope choice above.

    ``f8_near_miss_controls.py`` rewrites source files and restores them. If a
    future edit made this suite run it, an interrupted CI job could leave a
    mutated tree. The exclusion is asserted so it stays a decision rather than
    becoming an accident.
    """
    source = (pathlib.Path(__file__)).read_text()
    assert "f8_near_miss_controls.py\", (" not in source.replace(" ", "")
    module = _load("f8_near_miss_controls.py")
    assert callable(module.main), "entry point kept, but not invoked here"
