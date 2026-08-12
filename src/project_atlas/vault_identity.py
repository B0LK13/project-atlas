"""Canonical Vault identity mint/ensure for ``.atlas/vault.json``.

AS-DEMO-2.2-RECOVERY-ID-001 / D-PROJECT-ATLAS-CLOUD-DEMO-RECOVERY-019.

Product bootstrap (``atlas init``) must establish a recovery-capable Vault
identity before snapshot/restore become available. This module is the single
writer reused by Core scaffold and the control-plane ``atlas_agent install``
command — do not invent a second identity system inside backup/snapshot.

Safety contract:

- absent valid identity → mint once (UUID generated)
- valid existing identity with same ``vault_id`` → preserve bytes exactly
- valid existing identity with different ``vault_id`` → fail closed
- malformed / unreadable identity → fail closed (no auto-repair)
- symlink / reparse escape of the identity path → fail closed
- snapshot / restore remain non-minting consumers
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from atlas_contracts.agent_event import VaultIdentity
from atlas_contracts.identity import ensure_under_root
from atlas_contracts.versions import ID_PATTERN

DEFAULT_VAULT_ID = "atlas-main"
DEFAULT_VAULT_NAME = "Atlas Vault"
IDENTITY_RELATIVE = Path(".atlas") / "vault.json"


class VaultIdentityError(Exception):
    """Raised when Vault identity cannot be established safely."""


def identity_path(vault_root: Path) -> Path:
    """Return the canonical identity marker path under ``vault_root``."""
    return vault_root.expanduser() / IDENTITY_RELATIVE


def _require_identity_path_contained(vault_root: Path, marker: Path) -> Path:
    """Fail closed on symlink / junction / reparse escapes (SEC-ADV004B-A-002)."""
    # Check symlink-ness before exists() so dangling escapes are not misreported
    # as "missing" (VI-002).
    if marker.is_symlink():
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {marker}"
        )
    parent = marker.parent
    if parent.is_symlink():
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {parent}"
        )
    try:
        safe = ensure_under_root(vault_root, marker, label="vault identity")
    except ValueError as exc:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {marker}"
        ) from exc
    real_root = Path(os.path.realpath(vault_root))
    real_marker = Path(os.path.realpath(marker))
    try:
        real_marker.relative_to(real_root)
    except ValueError as exc:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {marker}"
        ) from exc
    return safe


def _dirfd_identity_write_supported() -> bool:
    """POSIX renameat containment needs O_DIRECTORY; Windows has neither.

    On Windows, ``os.O_DIRECTORY`` is absent and opening a directory with
    ``O_RDONLY`` raises ``PermissionError``, so the Linux dirfd path cannot run.
    """
    return hasattr(os, "O_DIRECTORY")


def _open_identity_dir_fd(vault_root: Path, atlas_dir: Path) -> int:
    """Open ``.atlas`` with O_DIRECTORY|O_NOFOLLOW for renameat containment."""
    if atlas_dir.is_symlink():
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {atlas_dir}"
        )
    try:
        ensure_under_root(vault_root, atlas_dir, label="vault identity directory")
    except ValueError as exc:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {atlas_dir}"
        ) from exc
    o_directory = getattr(os, "O_DIRECTORY", None)
    if o_directory is None:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {atlas_dir}"
        )
    flags = os.O_RDONLY | int(o_directory)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    try:
        dir_fd = os.open(atlas_dir, flags)
    except OSError as exc:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {atlas_dir}"
        ) from exc
    # Belt (Linux): the opened inode must still resolve under the vault root.
    proc_path = Path(f"/proc/self/fd/{dir_fd}")
    if proc_path.exists():
        try:
            opened = Path(os.path.realpath(proc_path))
            real_root = Path(os.path.realpath(vault_root))
            opened.relative_to(real_root)
        except (OSError, ValueError) as exc:
            with contextlib.suppress(OSError):
                os.close(dir_fd)
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {atlas_dir}"
            ) from exc
    return dir_fd


def _write_atomic_posix_dirfd(vault_root: Path, path: Path, content: str) -> None:
    """Atomically write identity using dirfd + renameat (closes VI-001 TOCTOU).

    Opening the parent with ``O_NOFOLLOW`` and renaming via that dirfd means a
    concurrent swap of ``vault/.atlas`` for a symlink cannot redirect the final
    link. Post-write containment verifies the path still resolves in-vault.
    """
    atlas_dir = path.parent
    atlas_dir.mkdir(parents=True, exist_ok=True)
    _require_identity_path_contained(vault_root, path)
    dir_fd = _open_identity_dir_fd(vault_root, atlas_dir)
    tmp_basename: str | None = None
    try:
        fd, tmp_abs = tempfile.mkstemp(
            dir=atlas_dir, prefix=f".{path.name}.", suffix=".tmp"
        )
        tmp_basename = os.path.basename(tmp_abs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            # Re-validate lexical parents before renameat (narrow residual race).
            if atlas_dir.is_symlink() or path.is_symlink():
                raise VaultIdentityError(
                    "refusing vault identity outside vault root "
                    f"(symlink/reparse escape): {path}"
                )
            _require_identity_path_contained(vault_root, path)
            # renameat via the held dirfd — parent path swap cannot redirect.
            os.rename(
                tmp_basename,
                path.name,
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
            )
            tmp_basename = None
        finally:
            if tmp_basename is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_basename, dir_fd=dir_fd)
        # Post-write: final path must remain contained and hold our bytes.
        safe = _require_identity_path_contained(vault_root, path)
        if not safe.is_file() or safe.read_text(encoding="utf-8") != content:
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {path}"
            )
    finally:
        with contextlib.suppress(OSError):
            os.close(dir_fd)


def _write_atomic_windows(vault_root: Path, path: Path, content: str) -> None:
    """Windows atomic identity write (no O_DIRECTORY / dirfd).

    Containment relies on pre/post symlink+realpath checks and ``os.replace``.
    Dirfd renameat is unavailable on Win32; do not invent a second identity
    format — same ``vault.json`` bytes contract as POSIX.
    """
    atlas_dir = path.parent
    atlas_dir.mkdir(parents=True, exist_ok=True)
    _require_identity_path_contained(vault_root, path)
    if atlas_dir.is_symlink() or path.is_symlink():
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {path}"
        )
    fd, tmp_abs = tempfile.mkstemp(
        dir=atlas_dir, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_abs)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if atlas_dir.is_symlink() or path.is_symlink() or tmp_path.is_symlink():
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {path}"
            )
        _require_identity_path_contained(vault_root, path)
        _require_identity_path_contained(vault_root, tmp_path)
        os.replace(tmp_path, path)
        tmp_path = Path()  # published; skip cleanup
        safe = _require_identity_path_contained(vault_root, path)
        if not safe.is_file() or safe.read_text(encoding="utf-8") != content:
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {path}"
            )
    except OSError as exc:
        raise VaultIdentityError(
            f"unable to write vault identity: {path} ({exc})"
        ) from exc
    finally:
        if tmp_path.parts:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)


def _write_atomic(vault_root: Path, path: Path, content: str) -> None:
    """Atomically write ``.atlas/vault.json`` with platform-appropriate safety."""
    if _dirfd_identity_write_supported():
        _write_atomic_posix_dirfd(vault_root, path, content)
    else:
        _write_atomic_windows(vault_root, path, content)


def _validate_vault_id(vault_id: str) -> str:
    import re

    if not isinstance(vault_id, str) or not re.fullmatch(ID_PATTERN, vault_id):
        raise VaultIdentityError(f"invalid vault_id: {vault_id!r}")
    return vault_id


def _parse_existing(raw: Any, *, marker: Path) -> VaultIdentity:
    if not isinstance(raw, dict):
        raise VaultIdentityError(f"invalid Atlas Vault identity: {marker}")
    try:
        return VaultIdentity.model_validate(
            {
                "schema_version": raw.get("schema_version", 1),
                "vault_id": raw.get("vault_id"),
                "vault_uuid": raw.get("vault_uuid"),
                "name": raw.get("name"),
            }
        )
    except Exception as exc:  # pydantic ValidationError and TypeError
        raise VaultIdentityError(f"invalid Atlas Vault identity: {marker}") from exc


def read_vault_identity(vault_root: Path) -> VaultIdentity:
    """Read and validate an existing Vault identity (never mints)."""
    root = vault_root.expanduser().resolve(strict=False)
    marker = identity_path(root)
    if not marker.exists():
        raise VaultIdentityError(f"Atlas Vault identity is missing: {marker}")
    safe = _require_identity_path_contained(root, marker)
    if not safe.is_file():
        raise VaultIdentityError(f"Atlas Vault identity is missing: {marker}")
    try:
        raw = json.loads(safe.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VaultIdentityError(f"unreadable Atlas Vault identity: {marker}: {exc}") from exc
    return _parse_existing(raw, marker=marker)


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 200:
        raise VaultIdentityError(f"invalid vault name: {name!r}")
    if "\x00" in name or any(ord(ch) < 32 for ch in name):
        raise VaultIdentityError(f"invalid vault name: {name!r}")
    return name


def ensure_vault_identity(
    vault_root: Path,
    *,
    vault_id: str = DEFAULT_VAULT_ID,
    name: str = DEFAULT_VAULT_NAME,
) -> VaultIdentity:
    """Mint or preserve the canonical ``.atlas/vault.json`` identity.

    Reuses the ``atlas_agent install`` semantics:

    - missing marker → create ``schema_version`` / ``vault_id`` / ``vault_uuid`` / ``name``
    - existing marker with the same ``vault_id`` → leave file unmodified
    - existing marker with a different ``vault_id`` → raise
    - malformed / escaped marker → raise (fail closed; no rotation)
    """
    wanted_id = _validate_vault_id(vault_id)
    wanted_name = _validate_name(name)
    root = vault_root.expanduser().resolve(strict=False)
    marker = identity_path(root)
    atlas_dir = marker.parent

    if atlas_dir.exists() or atlas_dir.is_symlink():
        if atlas_dir.is_symlink():
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {atlas_dir}"
            )
        try:
            ensure_under_root(root, atlas_dir, label="vault identity directory")
        except ValueError as exc:
            raise VaultIdentityError(
                "refusing vault identity outside vault root "
                f"(symlink/reparse escape): {atlas_dir}"
            ) from exc

    if marker.exists() or marker.is_symlink():
        # Existing path: validate + preserve or fail. Never overwrite.
        existing = read_vault_identity(root)
        if existing.vault_id != wanted_id:
            raise VaultIdentityError("existing Vault ID differs")
        return existing

    atlas_dir.mkdir(parents=True, exist_ok=True)
    try:
        ensure_under_root(root, atlas_dir, label="vault identity directory")
    except ValueError as exc:
        raise VaultIdentityError(
            "refusing vault identity outside vault root "
            f"(symlink/reparse escape): {atlas_dir}"
        ) from exc

    payload = {
        "schema_version": 1,
        "vault_id": wanted_id,
        "vault_uuid": str(uuid.uuid4()),
        "name": wanted_name,
    }
    # Match historical atlas_agent install formatting (indent=2, trailing newline).
    content = json.dumps(payload, indent=2) + "\n"
    try:
        _write_atomic(root, marker, content)
    except OSError as exc:
        raise VaultIdentityError(f"unable to write vault identity: {marker}: {exc}") from exc

    return VaultIdentity.model_validate(payload)
