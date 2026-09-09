"""AS-OBSIDIAN-CAPTURE-001-F18 — a write boundary that does not care how you got there.

F16 answers *are the known writers correct?* by sweeping them. Its own adversarial
work then proved the harder question is not answerable that way: the set of
writers is derived from imports, and a hand-rolled splice using
``Path.read_bytes`` and its own regex reaches operator bytes while naming none of
the protected-region primitives. No import-graph analysis can see it.

    STATIC_DISCOVERY != ARCHITECTURAL_ENFORCEMENT
    KNOWN_WRITER_SET != CLOSED_WRITER_SET

**The observation this package rests on.** Atlas's import graph is open, but the
*operating system interface* is not. However a writer computes its content, the
destination path receives bytes through a small, enumerable set of primitives:
``os.replace``, ``os.rename``, ``Path.write_bytes``, ``Path.write_text``, a raw
file descriptor, or ``open()`` in a write mode. A check installed there is
**independent of how the writer is spelled**.

So this module does not ask *which module wrote this*. It asks: on every write to
a path that already carried human regions, are those regions byte-identical
afterwards? A writer may reach that outcome through ``merge_protected_regions``
or by any other means. What it may not do is succeed while silently altering
bytes the operator owns.

    SUCCESSFUL_WRITE != AUTHORITY_TO_REWRITE_HUMAN_BYTES

**What this is and is not.** It is a *test-time* boundary. It observes writes
that tests actually execute, so a production path no test exercises is outside
it. That is a real limit and is stated as one -- see
``test_f18_the_residual_classes_are_named_and_measured``. It is emphatically not
a claim that bypass is impossible.
"""

from __future__ import annotations

import builtins
import functools
import importlib
import os
import pathlib
import shutil
import sys

import pytest
from human_content_boundary import HumanContentBoundary, enforced  # type: ignore[import-not-found]

GENERATED_START = "<!-- atlas:generated:start -->"
GENERATED_END = "<!-- atlas:generated:end -->"
OPERATOR = "OPERATOR BYTES"
REGION = f"<!-- BEGIN HUMAN: notes -->\n{OPERATOR}\n<!-- END HUMAN: notes -->"
PRIOR = f"{GENERATED_START}\nold\n{GENERATED_END}\n{REGION}\n"
PRESERVING = f"{GENERATED_START}\nnew\n{GENERATED_END}\n{REGION}\n"


def _clobber(text: str) -> str:
    return text.replace(OPERATOR, "CLOBBERED")


def _note(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    """Seed byte-exactly.

    `Path.write_text` opens in text mode, which rewrites `\n` to `\r\n` on
    Windows. Seeding that way made the FIXTURE the source of the byte
    difference the boundary then reported, so a correct write looked like
    damage. Windows CI caught it; POSIX never could.
    """
    path = tmp_path / name
    path.write_bytes(PRIOR.encode("utf-8"))
    return path


# --------------------------------------------------------------------------
# Every route is a callable that DAMAGES operator bytes. Each must be caught,
# whatever primitive it reaches for. The point of the list is that none of them
# imports a protected-region primitive in a way F16's derivation would see.
# --------------------------------------------------------------------------


def _hand_rolled_write_text(path: pathlib.Path) -> None:
    path.write_text(_clobber(path.read_bytes().decode()))


def _hand_rolled_write_bytes(path: pathlib.Path) -> None:
    path.write_bytes(_clobber(path.read_text()).encode())


def _own_atomic_writer(path: pathlib.Path) -> None:
    tmp = path.with_suffix(".stage")
    tmp.write_bytes(_clobber(path.read_text()).encode())
    os.replace(tmp, path)


def _own_rename_writer(path: pathlib.Path) -> None:
    tmp = path.with_suffix(".stage2")
    tmp.write_bytes(_clobber(path.read_text()).encode())
    os.rename(tmp, path)


def _via_capture_io(path: pathlib.Path) -> None:
    from project_atlas.capture_io import write_atomic_under_root

    write_atomic_under_root(
        path, _clobber(path.read_text()).encode(), root=path.parent, label="note"
    )


def _dynamic_import_then_clobber(path: pathlib.Path) -> None:
    module = importlib.import_module("project_atlas.protected" + "_regions")
    merge = getattr(module, "merge" + "_protected_regions")
    merged = merge(existing=path.read_text(), rendered=PRESERVING, path="n.md")
    path.write_text(_clobber(merged))


def _partial_wrapper(path: pathlib.Path) -> None:
    functools.partial(pathlib.Path.write_text)(path, _clobber(path.read_text()))


def _raw_fdopen(path: pathlib.Path) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(fd, "w") as handle:
        handle.write(_clobber(PRIOR))


def _raw_os_write(path: pathlib.Path) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_TRUNC)
    os.write(fd, _clobber(PRIOR).encode())
    os.close(fd)


def _shutil_copyfile(path: pathlib.Path) -> None:
    source = path.with_suffix(".source")
    source.write_text(_clobber(PRIOR))
    shutil.copyfile(source, path)


def _shutil_move(path: pathlib.Path) -> None:
    source = path.with_suffix(".source2")
    source.write_text(_clobber(PRIOR))
    shutil.move(str(source), str(path))


def _builtin_open(path: pathlib.Path) -> None:
    with builtins.open(path, "w") as handle:
        handle.write(_clobber(PRIOR))


#: Route name -> callable. Every one of these damages operator bytes.
BYPASS_ROUTES = {
    "hand-rolled splice via Path.write_text": _hand_rolled_write_text,
    "hand-rolled splice via Path.write_bytes": _hand_rolled_write_bytes,
    "a writer's own tmp + os.replace": _own_atomic_writer,
    "a writer's own tmp + os.rename": _own_rename_writer,
    "capture_io.write_atomic_under_root": _via_capture_io,
    "dynamic import, then clobber after merging": _dynamic_import_then_clobber,
    "functools.partial wrapper": _partial_wrapper,
    "raw descriptor via os.fdopen": _raw_fdopen,
    "raw descriptor via os.write": _raw_os_write,
    "shutil.copyfile over the note": _shutil_copyfile,
    "shutil.move over the note": _shutil_move,
    "builtins.open in write mode": _builtin_open,
}


def test_f18_every_bypass_route_is_caught(tmp_path: pathlib.Path) -> None:
    """The property: damage is detected regardless of how the write is spelled.

    None of these routes would appear in F16's import-derived writer set. Several
    do not import anything from `protected_regions` at all. That is the point --
    this boundary is installed at the OS interface, not in the import graph.
    """
    escaped: list[str] = []
    inapplicable: list[str] = []
    for index, (label, route) in enumerate(BYPASS_ROUTES.items()):
        note = _note(tmp_path, f"bypass{index}.md")
        before = note.read_bytes()
        with enforced() as boundary:
            try:
                route(note)
            except OSError as exc:
                # A route the platform refuses is not an escape -- nothing was
                # written, so there is nothing the boundary failed to see. The
                # canonical case is `os.rename` onto an existing file, which
                # overwrites on POSIX and raises WinError 183 on Windows.
                # Recorded by name so a route that silently stops working
                # everywhere shows up as shrinking coverage rather than as a
                # pass.
                if note.read_bytes() == before:
                    inapplicable.append(f"{label} ({type(exc).__name__})")
                    continue
                raise
        damaged = OPERATOR.encode() not in note.read_bytes()
        assert damaged, f"{label!r} did not actually damage the note; the route is inert"
        if not boundary.violations:
            escaped.append(label)
    assert not escaped, f"routes that damaged operator bytes undetected: {escaped}"
    # Non-vacuity: "no route escaped" must not be reachable by every route
    # being skipped. The bound is deliberately most of the list, not one.
    applicable = len(BYPASS_ROUTES) - len(inapplicable)
    assert applicable >= len(BYPASS_ROUTES) - 2, (
        f"only {applicable}/{len(BYPASS_ROUTES)} routes ran here; inapplicable: {inapplicable}"
    )


def test_f18_a_preserving_write_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """The negative side: the boundary must not fire on a correct write.

    Without this the whole thing could be `return [Violation(...)]` and every
    other assertion here would still pass.
    """
    note = _note(tmp_path, "ok.md")
    with enforced() as boundary:
        # Byte-exact spellings throughout. Text mode is not byte-preserving on
        # Windows, so writing `PRESERVING` through it would change the note and
        # the boundary would be right to say so -- see the test below, which
        # pins that as a real damage route rather than working around it.
        note.write_bytes(PRESERVING.encode("utf-8"))
        os.replace(*_staged(note, PRESERVING))
        with builtins.open(note, "wb") as handle:
            handle.write(PRESERVING.encode("utf-8"))
    assert not boundary.violations, f"a preserving write was flagged: {boundary.violations}"
    assert boundary.checked >= 3, f"the boundary did not observe the writes: {boundary.checked}"
    assert OPERATOR in note.read_text()


def _staged(note: pathlib.Path, content: str) -> tuple[pathlib.Path, pathlib.Path]:
    staged = note.with_suffix(".ok-stage")
    staged.write_bytes(content.encode())
    return staged, note


def test_f18_a_file_without_human_regions_is_not_this_boundarys_business(
    tmp_path: pathlib.Path,
) -> None:
    """Scope: only notes that already carry operator regions are protected.

    A generated-only artifact may be rewritten freely; claiming otherwise would
    make the boundary fire on ordinary Atlas output and be switched off.
    """
    plain = tmp_path / "generated-only.md"
    plain.write_text(f"{GENERATED_START}\nonly generated\n{GENERATED_END}\n")
    with enforced() as boundary:
        plain.write_text(f"{GENERATED_START}\ncompletely different\n{GENERATED_END}\n")
    assert not boundary.violations
    assert boundary.protected_writes == 0


def test_f18_an_authorised_rewrite_is_explicit_named_and_scoped(
    tmp_path: pathlib.Path,
) -> None:
    """How an exception is represented: a reason, a scope, and a record.

    This is the governance boundary. A test that deliberately corrupts a
    protected note to prove a guard fires must say so; production code should
    never need this, and a reviewer can grep for it.
    """
    note = _note(tmp_path, "authorised.md")
    reason = "deliberate corruption, proving a refusal fires"
    with enforced() as boundary, boundary.authorized(reason):
        note.write_text(_clobber(PRIOR))
    assert not boundary.violations, "an authorised rewrite must not register as a violation"
    assert OPERATOR not in note.read_text(), "the authorised rewrite did not happen"

    # The authorisation is scoped: outside the block the same write is a violation.
    note.write_text(PRIOR)
    with enforced() as boundary:
        note.write_text(_clobber(PRIOR))
    assert boundary.violations, "authorisation leaked outside its block"

    with enforced() as boundary, pytest.raises(ValueError, match="must state a reason"):
        boundary.authorized("   ").__enter__()


def test_f18_the_boundary_itself_can_fail(tmp_path: pathlib.Path) -> None:
    """A guard is evidence only if removing a hook makes a route escape.

    Each primitive is unhooked in turn and the route that depends on it must go
    undetected. Without this, the twelve-route table above could be passing
    because the routes are inert rather than because the boundary works.
    """
    depends_on = {
        "Path.write_bytes": _hand_rolled_write_bytes,
        "os.replace": _own_atomic_writer,
        "os.rename": _own_rename_writer,
        "builtins.open": _builtin_open,
    }
    unhooked = 0
    for index, (primitive, route) in enumerate(depends_on.items()):
        note = _note(tmp_path, f"unhooked{index}.md")
        before = note.read_bytes()
        boundary = HumanContentBoundary()
        boundary.install()
        try:
            # Put the real primitive back, leaving every other hook in place.
            _restore_one(boundary, primitive)
            route(note)
        except OSError:
            # Same platform caveat as the route table: `os.rename` onto an
            # existing file raises on Windows, so it cannot be a damage route
            # there and proves nothing about the hook either way.
            boundary.uninstall()
            if note.read_bytes() == before:
                continue
            raise
        else:
            boundary.uninstall()
        unhooked += 1
        assert OPERATOR.encode() not in note.read_bytes(), f"{primitive}: route did not damage"
        assert not boundary.violations, (
            f"unhooking {primitive} did not blind the boundary to the route that "
            "uses it, so that hook is not load-bearing and the table overstates"
        )
    assert unhooked >= len(depends_on) - 1, (
        f"only {unhooked}/{len(depends_on)} hooks were actually tested here"
    )


def _restore_one(boundary: HumanContentBoundary, primitive: str) -> None:
    saved = boundary._saved
    if primitive == "os.replace":
        os.replace = saved["os.replace"]
    elif primitive == "os.rename":
        os.rename = saved["os.rename"]
    elif primitive == "Path.write_bytes":
        pathlib.Path.write_bytes = saved["Path.write_bytes"]  # type: ignore[method-assign]
    elif primitive == "builtins.open":
        builtins.open = saved["builtins.open"]
    else:  # pragma: no cover - guarded by the caller's dict
        raise AssertionError(primitive)


def test_f18_the_residual_classes_are_named_and_measured(tmp_path: pathlib.Path) -> None:
    """What remains outside, stated as a test so it cannot quietly drift.

    `CLAIM_SCOPE <= MECHANISM_SCOPE`. The boundary covers the primitives Python
    code uses to land bytes. It does **not** cover a write that never passes
    through the interpreter -- a subprocess, a C extension, or `mmap`. This test
    demonstrates one such route escaping, so the limit is measured rather than
    asserted, and nobody can later read the twelve-route table as closure.
    """
    note = _note(tmp_path, "subprocess.md")
    import subprocess
    import sys

    with enforced() as boundary:
        subprocess.run(
            [sys.executable, "-c", f"open({str(note)!r}, 'w').write({_clobber(PRIOR)!r})"],
            check=True,
        )
    assert OPERATOR not in note.read_text(), "the subprocess route did not damage"
    assert not boundary.violations, (
        "a subprocess write was detected -- if this now works, the residual "
        "class documented here has narrowed and the record should say so"
    )


def test_f18_the_boundary_detects_damage_but_cannot_attribute_it(
    tmp_path: pathlib.Path,
) -> None:
    """The limit that decided the deployment, pinned so it cannot be forgotten.

    An earlier revision failed the whole session on violations whose innermost
    frame was under ``src/project_atlas``, on the theory that this separated
    "Atlas clobbered it" from "a test authored its own content". Measurement
    killed that theory, and this test is the measurement.

    The same damaging act, spelled two ways, attributes to two different places
    -- so the field names whichever helper *landed* the bytes, not whoever
    authored them. An atomic writer has no preservation duty; it writes what it
    is given. Anyone reading ``landed_via_atlas_helper`` as a responsibility
    signal, and gating on it, would be gating on plumbing.
    """
    from project_atlas.capture_io import write_atomic_under_root

    damaged = _clobber(PRIOR).encode()

    handed_to_helper = _note(tmp_path, "via-helper.md")
    with enforced() as first:
        write_atomic_under_root(handed_to_helper, damaged, root=tmp_path, label="note")

    written_directly = _note(tmp_path, "direct.md")
    with enforced() as second:
        written_directly.write_bytes(damaged)

    assert first.violations and second.violations, (
        "both spellings must be DETECTED -- that part works and is the point of the boundary"
    )
    assert first.violations[0].landed_via_atlas_helper is True
    assert second.violations[0].landed_via_atlas_helper is False, (
        "the two spellings of one act now attribute identically; if that is "
        "genuinely fixed, the report-only decision in tests/conftest.py should be "
        "revisited, because a sound attribution would make a hard gate possible"
    )


def test_f18_text_mode_writing_is_a_real_damage_route_where_it_translates(
    tmp_path: pathlib.Path,
) -> None:
    """Windows CI found this; POSIX cannot.

    `Path.write_text` and `open(path, "w")` translate `\\n` to the platform
    line ending. On Windows that rewrites an operator's LF bytes on a refresh
    they never asked for -- the same class of defect as the CRLF-translating
    *read* that `protected_regions.read_note_text` exists to prevent, arriving
    from the write side instead.

    The translation is **probed, not assumed from the platform name**, so this
    stays honest if a future Python changes the default. Where text mode is
    byte-transparent (POSIX) there is nothing to detect and the test says so
    rather than pretending to have measured something.
    """
    probe = tmp_path / "probe.txt"
    probe.write_text("a\nb")
    translates = probe.read_bytes() != b"a\nb"
    if not translates:
        pytest.skip(f"text mode is byte-transparent here ({sys.platform})")

    # Both text-mode spellings, because they reach disk by different hooks:
    # `Path.write_text` is verified after the bytes land, `builtins.open` at
    # descriptor close. A gap in either would be invisible to the other.
    for index, spelling in enumerate(("write_text", "open")):
        note = _note(tmp_path, f"textmode{index}.md")
        with enforced() as boundary:
            if spelling == "write_text":
                note.write_text(PRESERVING)
            else:
                with builtins.open(note, "w") as handle:
                    handle.write(PRESERVING)
        assert b"\r\n" in note.read_bytes(), f"{spelling}: fixture did not translate"
        assert boundary.violations, (
            f"{spelling} rewrote the operator's line endings and the boundary did "
            "not report it -- a translating write is damage even when every word "
            "still matches"
        )
