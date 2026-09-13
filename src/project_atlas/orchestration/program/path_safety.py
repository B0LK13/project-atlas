"""F01 / AT-013: one explicit filesystem boundary for program continuation.

Operator bindings may be absolute, but data components must be relative. A
binding is never inferred from a common ancestor. Reject links (including
Windows reparse points) in every existing component, including the root, and
repeat validation at IO sites. This is path validation, not an OS sandbox:
hostile concurrent directory replacement requires handle-relative IO throughout
the runtime and is not claimed to be prevented by a check followed by an open.
"""

from __future__ import annotations

import stat
from pathlib import Path, PureWindowsPath

from project_atlas.orchestration.program.models import ProgramError


class ContainmentError(ProgramError):
    code = "PROGRAM_PATH_CONTAINMENT"


def _syntax(path: Path | str, *, relative: bool = False) -> Path:
    text = str(path)
    windows = PureWindowsPath(text)
    if (
        not text
        or "\x00" in text
        or "\\" in text
        or ".." in text.split("/")
        or (relative and (Path(text).is_absolute() or windows.drive))
        or (windows.drive and not Path(text).is_absolute())
        or any(":" in part for part in Path(text).parts if part != Path(text).anchor)
    ):
        raise ContainmentError("unsafe path component")
    return Path(text)


def _no_links(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ContainmentError("cannot inspect path component") from exc
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ContainmentError("symlink or reparse point in governed path")


def trusted_root(root: Path) -> Path:
    """Validate an operator-supplied root; never broaden it implicitly."""
    path = _syntax(root).absolute()
    _no_links(path)
    resolved = path.resolve()
    if resolved == Path(resolved.anchor) or resolved == Path.home():
        raise ContainmentError("filesystem root and home are not governed roots")
    return resolved


def checked_path(path: Path, *, root: Path | None = None) -> Path:
    """Check a binding/IO target against its explicit root immediately before IO.

    Without a containing root, the caller supplies the target as a trusted
    binding. This mode still rejects traversal and links; queue-derived targets
    must always pass the independently selected governed root.
    """
    target = _syntax(path).absolute()
    boundary = trusted_root(root if root is not None else target.parent)
    if not target.is_relative_to(boundary):
        raise ContainmentError("path is outside the governed root")
    _no_links(target)
    resolved = target.resolve()
    if not resolved.is_relative_to(boundary):
        raise ContainmentError("resolved path is outside the governed root")
    return resolved


def child_path(root: Path, relative: Path | str) -> Path:
    """Join an untrusted relative component without normalising away traversal."""
    component = _syntax(relative, relative=True)
    return checked_path(root / component, root=root)


def check_children(directory: Path, *, root: Path) -> None:
    """Guard a flat durable namespace before calling an existing list reader."""
    directory = checked_path(directory, root=root)
    if directory.is_dir():
        for path in directory.iterdir():
            checked_path(path, root=root)
