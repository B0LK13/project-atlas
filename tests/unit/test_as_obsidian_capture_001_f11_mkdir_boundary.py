"""AS-OBSIDIAN-CAPTURE-001-F11 — the third failure site in each writer.

F6 closed the error boundary for two of the three ways an atomic note write can
fail: the read of the prior note, and `os.replace`. The third — creating the
note's parent directory — was left outside the guard in **both** writers, so a
blocked or unwritable parent escaped as a raw `OSError` past
`ObsidianProjectionError` / `GraphProjectionError`. A caller catching the domain
error did not catch this at all, which is exactly the defect F6 exists to
prevent, one step earlier in the same function.

Recorded in the F1-F4 residual register as "`_write_atomic`'s `mkdir` is outside
the new guard". Reproduced on current `main` at both sites before fixing:

    obsidian_projection._write_atomic  -> NotADirectoryError escaped
    graph_projections._promote         -> NotADirectoryError escaped

Both are reached by a plain file sitting where a directory must be — a stale or
tampered vault, or a path component an operator created by hand.

Scope: an error-boundary fix, not a policy change. The same writes fail; they
now fail inside the module's own exception type, naming the directory. Nothing
that succeeded before is refused now.
"""

from __future__ import annotations

import pathlib

import pytest

import project_atlas.graph_projections as gp
import project_atlas.obsidian_projection as op
from project_atlas.graph_projections import GraphProjectionError
from project_atlas.obsidian_projection import ObsidianProjectionError


def _blocked_parent(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A vault where the note's parent path component is a FILE, not a dir."""
    vault = tmp_path / "vault"
    vault.mkdir()
    blocker = vault / "blocked"
    blocker.write_bytes(b"i am a file, not a directory")
    return vault, blocker / "sub" / "note.md"


def test_f11_projection_mkdir_failure_stays_inside_the_error_boundary(
    tmp_path: pathlib.Path,
) -> None:
    vault, target = _blocked_parent(tmp_path)
    with pytest.raises(ObsidianProjectionError) as caught:
        op._write_atomic(target, b"content", vault=vault)
    message = str(caught.value)
    assert message.startswith("unwritable-note-directory:")
    assert "NotADirectoryError" in message
    assert str(target.parent) in message, "the operator needs the directory named"


def test_f11_graph_mkdir_failure_stays_inside_the_error_boundary(
    tmp_path: pathlib.Path,
) -> None:
    _, target = _blocked_parent(tmp_path)
    with pytest.raises(GraphProjectionError) as caught:
        gp._promote({target: b"content"})
    message = str(caught.value)
    assert message.startswith("unwritable-note-directory:")
    assert "NotADirectoryError" in message


def test_f11_a_raw_oserror_never_escapes_either_writer(tmp_path: pathlib.Path) -> None:
    """The property F6 established, now true at all three sites.

    Asserted as "no OSError escapes" rather than "a domain error is raised",
    because the defect was precisely that the domain type did not cover this
    path -- a test that only checked for the domain type would pass on a writer
    that raised nothing at all.
    """
    vault, target = _blocked_parent(tmp_path)
    for call in (
        lambda: op._write_atomic(target, b"c", vault=vault),
        lambda: gp._promote({target: b"c"}),
    ):
        try:
            call()
        except (ObsidianProjectionError, GraphProjectionError):
            pass
        except OSError as exc:  # pragma: no cover - the defect this pins
            pytest.fail(f"raw {type(exc).__name__} escaped the module boundary: {exc}")


def test_f11_nothing_is_left_behind_when_the_directory_cannot_be_made(
    tmp_path: pathlib.Path,
) -> None:
    """Fail-closed: a refused write leaves no staging residue of any name."""
    vault, target = _blocked_parent(tmp_path)
    before = {p for p in vault.rglob("*")}
    with pytest.raises(ObsidianProjectionError):
        op._write_atomic(target, b"content", vault=vault)
    with pytest.raises(GraphProjectionError):
        gp._promote({target: b"content"})
    assert {p for p in vault.rglob("*")} == before


def test_f11_a_writable_parent_is_still_created_normally(tmp_path: pathlib.Path) -> None:
    """Positive control: the guard must not stop directories being created."""
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "a" / "b" / "note.md"
    op._write_atomic(target, b"hello", vault=vault)
    assert target.read_bytes() == b"hello"
    assert target.parent.is_dir()
