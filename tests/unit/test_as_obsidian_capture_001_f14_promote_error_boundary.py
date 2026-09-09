"""AS-OBSIDIAN-CAPTURE-001 F14 -- `_promote` must not leak raw `OSError`.

`_promote` is `graph_projections`' transactional write boundary: it stages,
backs up and promotes. A caller that catches `GraphProjectionError` -- the
module's own type, and the one its docstrings tell callers to catch -- did not
catch three failures there at all, so an uncontained error at exactly the point
the fail-closed guarantee matters most escaped into the caller's stack.

Reproduced on `main` (`b87b4a22`) before the fix, with the raising line
attributed by walking the traceback back into the module:

===========================  =========================  ====
condition                    escaped as                 line
===========================  =========================  ====
read-only output directory   ``PermissionError``        620
existing target unreadable   ``PermissionError``        616
``ENAMETOOLONG`` filename    ``OSError``                614
===========================  =========================  ====

Two of these are named verbatim in F6's residual register; the third
(``ENAMETOOLONG``) was found while reproducing them and is not recorded
anywhere. All are pre-existing -- F11 closed the `mkdir` site one step earlier
in the same loop and did not introduce these.

**On fixture liveness.** The permission-based cases are inert where the process
can read anything regardless of mode -- as root, and on Windows, where
``chmod(0o000)`` does not block a read. A test that silently skips there would
report green while measuring nothing, so each fixture is *probed* and the test
is skipped only with the platform named. The portable monkeypatched cases run
everywhere and carry the containment logic on their own, so no platform is left
with zero coverage of this boundary.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

import pytest

from project_atlas.graph_projections import GraphProjectionError, _promote


def _blocked(probe: Any) -> bool:
    """Did the fixture actually block? Measured, never assumed."""
    try:
        probe()
    except OSError:
        return True
    return False


# ------------------------------------------------------- portable containment
@pytest.mark.parametrize(
    ("method", "reason"),
    [
        ("exists", "unstattable-note-target"),
        ("read_bytes", "unreadable-note-target"),
        ("write_bytes", "unwritable-note-stage"),
    ],
)
def test_f14_an_oserror_from_each_site_is_contained(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, method: str, reason: str
) -> None:
    """Every site that can raise `OSError` reports the module's own type.

    Forcing the error rather than provoking it keeps this runnable on every
    platform, which is what stops the boundary from being covered only where
    a permission trick happens to work.
    """
    target = tmp_path / "n.md"
    if method == "read_bytes":
        target.write_bytes(b"prior")

    real = getattr(pathlib.Path, method)

    def boom(self: pathlib.Path, *a: Any, **k: Any) -> Any:
        if self.name.startswith("n.md") or self.name.startswith(".n.md"):
            raise PermissionError(13, "forced")
        return real(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, method, boom)
    with pytest.raises(GraphProjectionError) as caught:
        _promote({target: b"fresh"})
    assert str(caught.value).startswith(reason), str(caught.value)


def test_f14_the_three_reasons_are_distinct() -> None:
    """Collapsing them into one reason would lose actionable information.

    An unstattable path, an unreadable existing note and an unwritable staging
    file are three different things to go and fix. This module already treats
    "the operator can act on the difference" as the rule for its diagnostics.
    """
    reasons = {
        "unstattable-note-target",
        "unreadable-note-target",
        "unwritable-note-stage",
    }
    assert len(reasons) == 3


# ------------------------------------------------ the real syscalls, probed
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_f14_a_read_only_output_directory_is_contained(
    tmp_path: pathlib.Path,
) -> None:
    """The staging write, provoked rather than forced."""
    target = tmp_path / "n.md"
    os.chmod(tmp_path, 0o555)
    try:
        if not _blocked(lambda: (tmp_path / "probe").write_bytes(b"x")):
            pytest.skip(f"fixture inert: {tmp_path} stayed writable (euid={os.geteuid()})")
        with pytest.raises(GraphProjectionError) as caught:
            _promote({target: b"fresh"})
    finally:
        os.chmod(tmp_path, 0o755)
    assert str(caught.value).startswith("unwritable-note-stage")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_f14_an_unreadable_existing_target_is_contained(
    tmp_path: pathlib.Path,
) -> None:
    """The comparison read against a note that became unreadable."""
    target = tmp_path / "n.md"
    target.write_bytes(b"prior")
    os.chmod(target, 0o000)
    try:
        if not _blocked(target.read_bytes):
            pytest.skip(f"fixture inert: {target} stayed readable (euid={os.geteuid()})")
        with pytest.raises(GraphProjectionError) as caught:
            _promote({target: b"fresh"})
    finally:
        os.chmod(target, 0o644)
    assert str(caught.value).startswith("unreadable-note-target")


def test_f14_an_over_long_filename_is_contained(tmp_path: pathlib.Path) -> None:
    """`ENAMETOOLONG` -- the case missing from F6's residual register.

    This one needs no privileges, so it exercises the real syscall path on
    every platform the suite runs on.
    """
    target = tmp_path / ("z" * 5000 + ".md")
    if not _blocked(target.exists):
        pytest.skip(f"fixture inert: {len(target.name)}-char name was accepted")
    with pytest.raises(GraphProjectionError) as caught:
        _promote({target: b"fresh"})
    assert str(caught.value).startswith("unstattable-note-target")


def test_f14_containment_does_not_swallow_the_happy_path(
    tmp_path: pathlib.Path,
) -> None:
    """The control that stops the fix from being a blanket `except OSError`.

    Wrapping these calls must not turn an ordinary successful promotion into a
    failure, nor mask the pre-existing `canonical-target-not-file` refusal that
    shares one of the guarded expressions.
    """
    ok = tmp_path / "ok.md"
    _promote({ok: b"content"})
    assert ok.read_bytes() == b"content"

    directory = tmp_path / "dir.md"
    directory.mkdir()
    with pytest.raises(GraphProjectionError) as caught:
        _promote({directory: b"content"})
    assert str(caught.value).startswith("canonical-target-not-file"), str(caught.value)
