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

_SITE_REASONS: tuple[tuple[str, str], ...] = (
    ("exists", "unstattable-note-target"),
    ("read_bytes", "unreadable-note-target"),
    ("write_bytes", "unwritable-note-stage"),
)


def _blocked(probe: Any) -> bool:
    """Did the fixture actually block? Measured, never assumed."""
    try:
        probe()
    except OSError:
        return True
    return False


def _residue(root: pathlib.Path) -> set[pathlib.Path]:
    return {p for p in root.rglob("*") if ".atlas-stage" in p.name or ".atlas-backup" in p.name}


def _force_oserror(tmp_path: pathlib.Path, method: str) -> str:
    """Raise a contained `GraphProjectionError` from one `_promote` site; return it.

    Restores the patched ``Path`` method itself so the helper can be called
    more than once in a test without stacking patches.
    """
    target = tmp_path / "n.md"
    if method == "read_bytes":
        target.write_bytes(b"prior")
    real = getattr(pathlib.Path, method)

    def boom(self: pathlib.Path, *a: Any, **k: Any) -> Any:
        if self.name.startswith("n.md") or self.name.startswith(".n.md"):
            raise PermissionError(13, "forced")
        return real(self, *a, **k)

    setattr(pathlib.Path, method, boom)
    try:
        with pytest.raises(GraphProjectionError) as caught:
            _promote({target: b"fresh"})
        return str(caught.value)
    finally:
        setattr(pathlib.Path, method, real)


# ------------------------------------------------------- portable containment
@pytest.mark.parametrize(("method", "reason"), _SITE_REASONS)
def test_f14_an_oserror_from_each_site_is_contained(
    tmp_path: pathlib.Path, method: str, reason: str
) -> None:
    """Every site that can raise `OSError` reports the module's own type.

    Forcing the error rather than provoking it keeps this runnable on every
    platform, which is what stops the boundary from being covered only where
    a permission trick happens to work.
    """
    message = _force_oserror(tmp_path, method)
    assert message.startswith(reason), message


def test_f14_the_three_reasons_are_distinct(tmp_path: pathlib.Path) -> None:
    """Distinctness is measured from live `_promote` errors, not a set literal.

    A prior revision asserted ``len({"a","b","c"}) == 3``. That cannot fail
    when all three sites emit the same prefix. Each site is provoked here and
    the prefixes must be pairwise distinct.
    """
    prefixes: list[str] = []
    for method, expected in _SITE_REASONS:
        site = tmp_path / method
        site.mkdir()
        message = _force_oserror(site, method)
        prefix = message.split(":", 1)[0]
        assert prefix == expected, message
        prefixes.append(prefix)
    assert len(set(prefixes)) == 3, prefixes


def test_f14_had_original_does_not_re_stat(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second ``exists()`` after staging was a fourth raw-``OSError`` leak.

    Independent verification of #757 found ``had_original=path.exists()``
    unguarded. ``had_original`` is now the ``is_file()`` result already
    captured inside the guarded read. A second ``exists()`` that raises must
    not be required for a successful promote of an existing file.
    """
    target = tmp_path / "n.md"
    target.write_bytes(b"prior")
    real = pathlib.Path.exists
    calls = {"n": 0}

    def once_then_boom(self: pathlib.Path, *a: Any, **k: Any) -> Any:
        if self.name != "n.md":
            return real(self, *a, **k)
        calls["n"] += 1
        if calls["n"] > 1:
            raise PermissionError(13, "second exists")
        return real(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "exists", once_then_boom)
    _promote({target: b"fresh"})
    assert target.read_bytes() == b"fresh"
    assert calls["n"] == 1


@pytest.mark.parametrize(("method", "reason"), _SITE_REASONS)
def test_f14_nothing_is_left_behind_when_containment_fires(
    tmp_path: pathlib.Path, method: str, reason: str
) -> None:
    """A contained staging failure leaves no ``.atlas-stage`` / ``.atlas-backup``."""
    target = tmp_path / "n.md"
    if method == "read_bytes":
        target.write_bytes(b"prior")
        before_bytes: bytes | None = target.read_bytes()
    else:
        before_bytes = None
    before = {p for p in tmp_path.rglob("*")}
    message = _force_oserror(tmp_path, method)
    assert message.startswith(reason), message
    assert _residue(tmp_path) == set()
    assert {p for p in tmp_path.rglob("*")} == before
    if before_bytes is not None:
        assert target.read_bytes() == before_bytes


# ------------------------------------------------ the real syscalls, probed
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_f14_a_read_only_output_directory_is_contained(
    tmp_path: pathlib.Path,
) -> None:
    """The staging write, provoked rather than forced."""
    target = tmp_path / "n.md"
    original_mode = tmp_path.stat().st_mode & 0o777
    os.chmod(tmp_path, 0o555)
    try:
        if not _blocked(lambda: (tmp_path / "probe").write_bytes(b"x")):
            pytest.skip(f"fixture inert: {tmp_path} stayed writable (euid={os.geteuid()})")
        with pytest.raises(GraphProjectionError) as caught:
            _promote({target: b"fresh"})
    finally:
        os.chmod(tmp_path, original_mode)
    assert str(caught.value).startswith("unwritable-note-stage")
    assert _residue(tmp_path) == set()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_f14_an_unreadable_existing_target_is_contained(
    tmp_path: pathlib.Path,
) -> None:
    """The comparison read against a note that became unreadable."""
    target = tmp_path / "n.md"
    target.write_bytes(b"prior")
    original_mode = target.stat().st_mode & 0o777
    os.chmod(target, 0o000)
    try:
        if not _blocked(target.read_bytes):
            pytest.skip(f"fixture inert: {target} stayed readable (euid={os.geteuid()})")
        with pytest.raises(GraphProjectionError) as caught:
            _promote({target: b"fresh"})
    finally:
        os.chmod(target, original_mode)
    assert str(caught.value).startswith("unreadable-note-target")
    assert target.read_bytes() == b"prior"
    assert _residue(tmp_path) == set()


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
