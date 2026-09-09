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
  them in a ``finally``. Running that inside CI would leave a broken tree if it
  were interrupted, so it is **not executed here** — only checked to import
  cleanly and still expose its entry point. Rot is caught; destruction is not
  risked.
* ``seal_retracted_claim_sweep.py`` over-reports by design and needs a human to
  classify its hits, so a pass/fail assertion on its exit code would be wrong.
  It too is **import- and interface-checked** only.

**How the exclusion is enforced, and what it does not reach.** Two layers, after
two weaker revisions. :func:`_fuse` replaces the mutating instrument's ``main``
with a tripwire at load time; that is the load-bearing layer and it is shape
independent — every route through :func:`_load` raises, whatever the call looks
like. :func:`_executing_references_to` is the second layer, a static scan for the
primitives that bypass :func:`_load` altogether (``subprocess``, ``runpy``,
``os``, ``importlib``, ``exec``), resolved through import aliases and through
names bound to string literals.

Neither reaches a path that both bypasses :func:`_load` *and* names the script
in a way no constant resolves — a filename assembled from fragments at runtime,
or read from another file. That residue is real. It is recorded rather than
implied away, because the first two revisions of this guard were each defeated
by a shape their author had not imagined, and the honest response is to say
where the third one ends rather than to claim it ends nowhere.

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

import ast
import importlib.util
import os
import pathlib
import subprocess
import sys
import types

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "docs" / "scripts"

#: The one instrument that rewrites source files. Never executed from here.
_MUTATING = "f8_near_miss_controls.py"

#: Each instrument's own public entry points, pinned so a rename or a refactor
#: fails here rather than rotting silently.
#:
#: An earlier revision called these "the callable each record names". Measured
#: against every file under ``docs/evidence/`` plus ``WORKLOG.md`` and
#: ``docs/backlog.md``, that is false: of these ten attributes only ``main``
#: appears at all, and only as ordinary prose (682 occurrences of the word).
#: ``NAMED``, ``FRAGMENTS``, ``CONTROLS`` and ``RETRACTION`` appear zero times.
#: The list is derived from the scripts, not from the records -- which still
#: catches rot, but is a weaker thing than the earlier comment claimed.
#:
#: Measured at the same time, and worth recording rather than quietly fixing:
#: ``seal_retracted_claim_sweep.py`` is cited by **no** evidence record, backlog
#: line or WORKLOG line anywhere in the repository. It was committed as
#: reproducible evidence for a claim sweep and nothing refers to it. That is the
#: same rot this module exists to catch, one level further out, and it is not in
#: this package's scope to fix.
CITED = {
    "f9_diagnostic_parity.py": ("main", "outcome", "NAMED", "FRAGMENTS"),
    "f8_near_miss_controls.py": ("main", "CONTROLS", "ANCHOR"),
    "seal_retracted_claim_sweep.py": ("sweep", "CLAIMS", "RETRACTION"),
}


def _invalidate_cached_bytecode(path: pathlib.Path) -> None:
    """Drop any ``__pycache__`` entry for ``path`` so the next load recompiles.

    Extracted so it can be tested against a throwaway file rather than against a
    committed instrument -- this suite must not mutate those, which is the whole
    subject of the exclusion below.
    """
    cached = pathlib.Path(importlib.util.cache_from_source(str(path)))
    cached.unlink(missing_ok=True)


def _fuse(module: types.ModuleType) -> None:
    """Replace the mutating instrument's entry point with a tripwire.

    This is the load-bearing half of the exclusion, and it is **shape
    independent**: every route through :func:`_load` is covered whatever the
    call looks like -- the module-level ``_MUTATING`` constant, an alias, a
    walrus, a tuple target, an annotated assignment, ``getattr``, a helper
    function, a binding made at module level and called elsewhere. A static
    check has to enumerate those; a fuse does not.

    The real callable is asserted to exist before it is replaced, so the
    interface check above still means what it says.
    """
    real = getattr(module, "main", None)
    assert callable(real), f"{_MUTATING} lost its main() entry point"

    def tripwire(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"{_MUTATING} was EXECUTED by this suite. It rewrites files under "
            "src/ and restores them in a finally block; an interrupted CI job "
            "would leave the tree mutated. It is deliberately import- and "
            "interface-checked here, never run."
        )

    tripwire.__wrapped__ = real  # type: ignore[attr-defined]
    module.main = tripwire  # type: ignore[assignment]


def _load(name: str) -> types.ModuleType:
    path = SCRIPTS / name
    # Force a fresh compile. `exec_module` accepts a cached .pyc whose header
    # (mtime, size) still matches the source, so an edit that keeps the byte
    # length and lands in the same second runs STALE bytecode. Verification
    # demonstrated exactly that here, and I reproduced it: with the source
    # patched and its mtime restored, the loaded module executed the OLD code
    # while the file on disk said something else.
    #
    # That is inert in CI, which always has a fresh checkout, and live in the
    # local edit-test loop -- which is precisely where the negative controls for
    # this lane get run. A control that measures a file it is not executing is
    # worse than no control, and this lane has already been misled by one.
    _invalidate_cached_bytecode(path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if name == _MUTATING:
        _fuse(module)
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


#: Module roots whose callables start a process or execute code. Matched after
#: resolving import aliases, so ``import subprocess as sp`` is not an escape.
_EXEC_MODULES = frozenset({"subprocess", "runpy", "os", "importlib", "pty", "multiprocessing"})

#: Builtins that execute source directly.
_EXEC_BUILTINS = frozenset({"exec", "eval", "compile", "__import__"})


class _SubstituteConstants(ast.NodeTransformer):
    """Replace names bound to string literals with those literals.

    Without this the detector only sees ``ast.Constant`` arguments, so
    ``_load(_MUTATING)`` -- the module's own constant, on the very line the
    guard test writes -- reads as an unknown name and slips through. That was
    the largest hole verification found, and it was the most idiomatic form
    available to the next maintainer.
    """

    def __init__(self, consts: dict[str, str]) -> None:
        self.consts = consts

    def visit_Name(self, node: ast.Name) -> ast.AST:
        value = self.consts.get(node.id)
        return ast.Constant(value=value) if isinstance(value, str) else node


def _string_constants(tree: ast.AST) -> dict[str, str]:
    """Every ``NAME = "literal"``, at any scope, including annotated targets."""
    consts: dict[str, str] = {}
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = value.value
    return consts


def _exec_roots(tree: ast.AST) -> set[str]:
    """Local names that reach an execution primitive, following import aliases."""
    roots = set(_EXEC_BUILTINS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _EXEC_MODULES:
                    roots.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and (
            (node.module or "").split(".")[0] in _EXEC_MODULES
        ):
            roots.update(alias.asname or alias.name for alias in node.names)
    return roots


def _executing_references_to(source: str, script: str) -> list[str]:
    """Call sites in ``source`` that would run ``script`` without going via ``_load``.

    Scope, stated precisely, because a guard whose limits are unstated invites
    exactly the over-reading this package exists to prevent. This finds a call
    to an execution primitive -- ``subprocess``/``runpy``/``os``/``importlib``,
    or ``exec``/``eval``/``compile`` -- that mentions the script, after
    resolving import aliases and substituting names bound to string literals.

    It does **not** find a path that neither routes through :func:`_load` nor
    names the script through a resolvable constant: a filename assembled from
    fragments at runtime, read from a file, or reached through a dynamically
    built attribute. Those are covered, if at all, by :func:`_fuse`, which is
    shape independent for everything that loads through :func:`_load` -- and by
    nothing at all if a path does neither. That residue is real and is
    deliberately recorded rather than papered over.
    """
    tree = ast.parse(source)
    consts = _string_constants(tree)
    roots = _exec_roots(tree)
    resolved = _SubstituteConstants(consts).visit(ast.parse(source))
    ast.fix_missing_locations(resolved)

    found: list[str] = []
    for node in ast.walk(resolved):
        if not isinstance(node, ast.Call):
            continue
        callee = ast.unparse(node.func)
        root = callee.split(".")[0].split("(")[0]
        if root not in roots:
            continue
        if script in ast.unparse(node):
            found.append(f"line {node.lineno}: {callee}(... {script} ...)")
    return found


def test_f12_the_mutating_instrument_is_not_executed_by_this_suite() -> None:
    """Guard the deliberate scope choice above, in two independent layers.

    ``f8_near_miss_controls.py`` rewrites source files and restores them in a
    ``finally``. If a future edit made this suite run it, an interrupted CI job
    would leave a mutated tree. The exclusion has to stay a decision rather than
    becoming an accident.

    **Two earlier revisions of this guard were weaker than they read.**

    The first asserted a substring: ``'f8_near_miss_controls.py", ('`` not in
    ``source.replace(" ", "")``. The needle contains a space and the haystack had
    every space stripped, so it could never match under any edit. Two review bots
    caught it independently.

    The second replaced that with a static AST detector. Better, but verification
    showed 15 of 20 execution paths still slipped past it -- including
    ``_load(_MUTATING).main()``, using the module's own constant, on the very
    line this test writes below. A maintainer copying that line and appending
    ``.main()`` defeated the whole guard. Enumerating call shapes is an arms race
    the guard loses.

    So the load-bearing layer is no longer static. :func:`_fuse` replaces the
    instrument's ``main`` with a tripwire at load time, which is **shape
    independent**: aliasing, a walrus, a tuple target, ``getattr``, a helper
    function, a module-level binding -- every route through :func:`_load` raises,
    whatever it looks like. :func:`_executing_references_to` is now the second
    layer, covering the primitives that bypass :func:`_load` entirely.

    Each layer carries its own positive control, because a guard that cannot be
    shown to fire is indistinguishable from one that is broken.
    """
    source = pathlib.Path(__file__).read_text()

    # Layer 2 control. `f9_diagnostic_parity.py` IS executed here as a script,
    # so a detector reporting nothing for it is broken rather than reassuring.
    control = _executing_references_to(source, "f9_diagnostic_parity.py")
    assert control, (
        "positive control: the parity instrument is executed here via subprocess, "
        "so the detector must find that call; it found nothing, which means the "
        "detector is broken and its silence about the mutating script is worthless"
    )

    running = _executing_references_to(source, _MUTATING)
    assert not running, (
        f"this suite would RUN the source-mutating instrument at: {running}. "
        "It rewrites files under src/ and restores them; an interrupted CI job "
        "would leave the tree mutated."
    )

    # Layer 1, and its control in the same breath: the entry point is still
    # present and callable -- which is what the evidence record depends on --
    # and calling it here raises rather than mutating anything.
    module = _load(_MUTATING)
    assert callable(module.main), "entry point kept, but not invoked here"
    with pytest.raises(AssertionError, match="was EXECUTED by this suite"):
        module.main()
    assert callable(module.main.__wrapped__), "the real entry point must survive the fuse"


def test_f12_the_fuse_survives_every_binding_shape() -> None:
    """The shapes that defeated the static detector must now all raise.

    Each of these was measured passing the previous revision's guard. They are
    exercised rather than pattern-matched, so this cannot rot into another
    assertion about source text.
    """
    shapes: list[tuple[str, types.ModuleType]] = [
        ("module-level constant", _load(_MUTATING)),
        ("string literal", _load("f8_near_miss_controls.py")),
    ]
    aliased = _load(_MUTATING)
    shapes.append(("alias", aliased))
    if (walrus := _load(_MUTATING)) is not None:
        shapes.append(("walrus", walrus))
    annotated: types.ModuleType = _load(_MUTATING)
    shapes.append(("annotated assignment", annotated))

    for label, module in shapes:
        with pytest.raises(AssertionError, match="was EXECUTED by this suite"):
            module.main()
        with pytest.raises(AssertionError, match="was EXECUTED by this suite"):
            # B009 is suppressed deliberately: the constant getattr IS the shape
            # under test. It defeated the previous revision's detector, which
            # only matched `ast.Attribute` callees, so it has to be exercised
            # literally rather than rewritten into the idiom ruff prefers.
            getattr(module, "main")()  # noqa: B009
        assert callable(module.main.__wrapped__), label


def test_f12_the_fuse_leaves_the_other_instruments_alone() -> None:
    """Negative side: only the mutating instrument is fused.

    Without this, a fuse that accidentally wrapped everything would make the
    parity test's real execution silently impossible to distinguish from a
    tripwire, and the module would still be green.
    """
    for name in sorted(CITED):
        module = _load(name)
        fused = hasattr(getattr(module, "main", None), "__wrapped__")
        assert fused == (name == _MUTATING), f"{name}: fused={fused}"


#: Synthetic sources, each a shape verification measured slipping past the
#: previous revision of the detector. They are exercised against the detector
#: directly rather than through this file, because this file must not itself
#: contain an execution path -- which is precisely why the earlier revisions'
#: "detector is live on this file" control could not reach these shapes.
_MUST_DETECT = {
    "module-level constant": (
        '_M = "f8_near_miss_controls.py"\n'
        "import runpy\n"
        "def f():\n"
        "    runpy.run_path(_M)\n"
    ),
    "aliased subprocess": (
        "import subprocess as sp\n"
        "def f():\n"
        '    sp.run(["python", "f8_near_miss_controls.py"])\n'
    ),
    "from-import of an exec primitive": (
        "from runpy import run_path\n"
        "def f():\n"
        '    run_path("f8_near_miss_controls.py")\n'
    ),
    "exec of the file's text": (
        "def f():\n"
        '    exec(open("f8_near_miss_controls.py").read())\n'
    ),
    "os.system": (
        "import os\n"
        "def f():\n"
        '    os.system("python f8_near_miss_controls.py")\n'
    ),
    "annotated constant": (
        '_M: str = "f8_near_miss_controls.py"\n'
        "import runpy\n"
        "def f():\n"
        "    runpy.run_path(_M)\n"
    ),
}

#: Shapes the detector must NOT flag, so it is not merely returning everything.
_MUST_NOT_DETECT = {
    "a bare mention in a string": '_M = "f8_near_miss_controls.py"\n',
    "a non-executing call": (
        "import pathlib\n"
        "def f():\n"
        '    pathlib.Path("f8_near_miss_controls.py").read_text()\n'
    ),
    "a different script": (
        "import runpy\n"
        "def f():\n"
        '    runpy.run_path("f9_diagnostic_parity.py")\n'
    ),
}


def test_f12_the_detector_finds_the_shapes_that_defeated_its_predecessor() -> None:
    """Pin the detector's own machinery, not just its verdict on this file.

    Verification found 15 of 20 execution shapes slipping past the previous
    revision. The fixes -- resolving names bound to string literals, and
    following import aliases -- are what closed them. Nothing in this file
    exercises either: `f9_diagnostic_parity.py` is named by a plain literal in a
    plain `subprocess.run`, so removing constant substitution entirely left the
    suite green. That is the mechanism-unpinned failure this lane keeps
    producing, so it is pinned here directly.

    This also makes a *targeted* blinding of the detector fail. Stubbing it to
    return `[]` only for `_MUTATING` passed every other assertion in this module.
    """
    missed = [
        label
        for label, source in _MUST_DETECT.items()
        if not _executing_references_to(source, _MUTATING)
    ]
    assert not missed, f"the detector no longer finds: {missed}"

    flagged = [
        label
        for label, source in _MUST_NOT_DETECT.items()
        if _executing_references_to(source, _MUTATING)
    ]
    assert not flagged, f"the detector flags shapes that do not execute: {flagged}"


def _load_from(path: pathlib.Path, *, invalidate: bool) -> types.ModuleType:
    """The loader body, parameterised, so the cache behaviour can be measured."""
    if invalidate:
        _invalidate_cached_bytecode(path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f12_a_stale_pyc_cannot_make_an_instrument_report_the_wrong_thing(
    tmp_path: pathlib.Path,
) -> None:
    """A control that measures a file it is not executing is worse than none.

    `exec_module` accepts a cached `.pyc` whose header `(mtime, size)` still
    matches the source, so an edit that keeps the byte length and lands in the
    same second runs STALE bytecode. Verification found this and I reproduced
    it: the loaded module executed the old code while the file on disk said
    something else. Inert in CI, which always has a fresh checkout -- live in
    the local edit-test loop, which is exactly where this lane runs its negative
    controls, and this lane has already been misled by a control reading a stale
    snapshot.

    Both halves are asserted. Without the invalidation the stale read is
    reproduced here, so this is a measurement rather than a claim; with it the
    module recompiles.
    """
    script = tmp_path / "instrument_under_test.py"
    script.write_text('MARKER = "OLD"\n')
    original = script.read_bytes()
    stat = script.stat()

    def mutate_in_place() -> None:
        """Same byte length, same mtime -- the shape the pyc header cannot see."""
        script.write_bytes(original.replace(b'"OLD"', b'"NEW"'))
        os.utime(script, (stat.st_atime, stat.st_mtime))
        assert script.stat().st_size == stat.st_size
        assert script.stat().st_mtime == stat.st_mtime

    # Negative control: the hazard is real, and reproduced right here.
    _load_from(script, invalidate=False)
    mutate_in_place()
    assert _load_from(script, invalidate=False).MARKER == "OLD", (
        "the stale-bytecode hazard did not reproduce, so the assertion below "
        "would pass for the wrong reason"
    )

    # The fix.
    script.write_bytes(original)
    os.utime(script, (stat.st_atime, stat.st_mtime))
    _load_from(script, invalidate=True)
    mutate_in_place()
    assert _load_from(script, invalidate=True).MARKER == "NEW"
