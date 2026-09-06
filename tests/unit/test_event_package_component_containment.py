"""Event-package components may not reach outside the source root.

`_confined` places the package *directory* inside the source root, and
`_raw_inventory` intends to refuse a symlinked package -- its error message
says so. But that check runs on an already-resolved path, so it never fires,
and confining a directory says nothing about where its contents point.

A component symlink therefore made an arbitrary file outside the root readable
as event evidence. Reproduced against `7a8f977d` before the fix: the recorded
`event.md` hash equalled the hash of a file outside the root, and reading the
component returned that file's bytes -- which is what ingestion copies into
the Vault for a package it accepts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from atlas_contracts.event_package import (
    EVENT_PACKAGE_FILES,
    PackageValidationError,
    _raw_inventory,
)

PACKAGE_PATH = ".atlas-inbox/agent-events/proj/evt-1"


def _package(root: Path, *, relative: str = PACKAGE_PATH) -> Path:
    package = root.joinpath(*relative.split("/"))
    package.mkdir(parents=True)
    return package


def _fill(package: Path, *, skip: str | None = None) -> None:
    for name in sorted(EVENT_PACKAGE_FILES):
        if name != skip:
            (package / name).write_text("{}\n", encoding="utf-8")


@pytest.mark.parametrize("component", sorted(EVENT_PACKAGE_FILES))
def test_component_symlinked_outside_the_root_is_refused(
    tmp_path: Path, component: str
) -> None:
    """Every component, not just the one that happened to be tested."""
    root = tmp_path / "source"
    package = _package(root)
    _fill(package, skip=component)
    outside = tmp_path / "outside.md"
    outside.write_text("OUTSIDE-CONTENT-THAT-MUST-NOT-BE-INGESTED\n", encoding="utf-8")
    (package / component).symlink_to(outside)

    with pytest.raises(PackageValidationError, match="component is symlinked"):
        _raw_inventory(root, PACKAGE_PATH)


def test_the_refusal_happens_before_any_outside_bytes_are_hashed(
    tmp_path: Path,
) -> None:
    """The hash is the evidence identity, so it must never be the outside file's.

    Before the fix this assertion was the defect: `hashes["event.md"]` equalled
    the sha256 of a file the source root does not contain.
    """
    root = tmp_path / "source"
    package = _package(root)
    _fill(package, skip="event.md")
    outside = tmp_path / "outside.md"
    outside.write_bytes(b"OUTSIDE\n")
    (package / "event.md").symlink_to(outside)
    outside_digest = hashlib.sha256(outside.read_bytes()).hexdigest()

    with pytest.raises(PackageValidationError):
        _, hashes = _raw_inventory(root, PACKAGE_PATH)
        assert hashes["event.md"] != outside_digest, "outside content was hashed as evidence"


def test_a_component_symlinked_inside_the_root_is_also_refused(
    tmp_path: Path,
) -> None:
    """Containment is not the only reason to refuse.

    An in-root target is confined, but the component's identity is still the
    link rather than the bytes, so the package's own hash would describe a
    file it does not contain. The verdict is about the component being a
    symlink, not about where it points.
    """
    root = tmp_path / "source"
    package = _package(root)
    _fill(package, skip="event.md")
    inside = root / "elsewhere.md"
    inside.write_text("in-root\n", encoding="utf-8")
    (package / "event.md").symlink_to(inside)

    with pytest.raises(PackageValidationError, match="component is symlinked"):
        _raw_inventory(root, PACKAGE_PATH)


def test_an_intra_root_aliased_package_directory_is_refused(tmp_path: Path) -> None:
    """The module's own symlinked-package refusal, made to fire.

    It inspects a path `_confined` has already resolved, so it never fired and
    its error string was unreachable. This is repair rather than policy: the
    verdict is the one the module already declares, and `discovery.py`
    enforces the same shape at its call site.
    """
    root = tmp_path / "source"
    real = _package(root)
    _fill(real)
    alias = real.parent / "evt-alias"
    alias.symlink_to(real)

    with pytest.raises(PackageValidationError, match="missing or symlinked"):
        _raw_inventory(root, ".atlas-inbox/agent-events/proj/evt-alias")


def test_an_ordinary_package_still_loads(tmp_path: Path) -> None:
    """The refusal must not cost a legitimate package."""
    root = tmp_path / "source"
    package = _package(root)
    _fill(package)

    resolved, hashes = _raw_inventory(root, PACKAGE_PATH)

    assert resolved == package.resolve()
    assert sorted(hashes) == sorted(EVENT_PACKAGE_FILES)
