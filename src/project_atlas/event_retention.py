"""AS-INT-009 — Deterministic raw-package and receipt retention policy.

Owns retention of Core-ingested agent-event raw packages and paired receipts:

- ``sources/agent-events/<project-id>/<event-id>/``
- ``receipts/agent-events/<project-id>/<event-id>.yaml``

Caps are count and/or total byte size only (NFR-001: no wall-clock freshness).
Ordering is lexicographic on ``project_id/event_id``; excess units are dropped
from the front of the sorted list (same deterministic "keep newest by order"
pattern as AS-OBS-002 stream retention).

Hard rules (INT9-FR-003 / INT9-FR-007):
- Fail closed on malformed retention config.
- Never delete Layer B concept notes or paths outside the two allowed roots.
- Do not rewrite ``recover_promote_orphans`` / ``_promote``.
- Do not invent removal tombstones in projections (AS-INT-010 owns that).
- Do not dual-own ``apps/web``, PILOT invent, or open REL-001.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from project_atlas.schema import validate_record

GENERATOR_ID = "atlas-int-009"
POLICY_SCHEMA = "event-retention-policy"
REPORT_SCHEMA = "event-retention-report"
POLICY_RELATIVE = Path(".atlas") / "retention-policy.json"
REPORT_RELATIVE = Path("generated") / "ops" / "retention-report.json"

RAW_PACKAGES_ROOT = Path("sources") / "agent-events"
RECEIPTS_ROOT = Path("receipts") / "agent-events"

DEFAULT_MAX_PACKAGES = 10_000
DEFAULT_MAX_BYTES = 256 * 1024 * 1024

# Paths that must never be deleted by this helper (Layer B / authority / peers).
_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "projects/",
    "01-portfolio/",
    "00-system/",
    "concepts/",
    "relationships/",
    "state/",
    "quarantine/",
    "generated/indexes/",
    "generated/portfolio/",
    "apps/",
)


class RetentionError(ValueError):
    """Raised when retention config or apply cannot proceed safely."""


@dataclass(frozen=True)
class RetentionUnit:
    """One retainable package/receipt pair identified by project + event."""

    project_id: str
    event_id: str
    package_dir: Path | None
    receipt_path: Path | None
    size_bytes: int

    @property
    def unit_key(self) -> str:
        return f"{self.project_id}/{self.event_id}"


def _inside(vault: Path, path: Path) -> Path:
    resolved_vault = vault.expanduser().resolve()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(resolved_vault):
        raise RetentionError(f"path escapes vault root: {path}")
    return resolved


def _posix_rel(vault: Path, path: Path) -> str:
    return path.resolve().relative_to(vault.resolve()).as_posix()


def _assert_allowed_delete(vault: Path, path: Path) -> Path:
    target = _inside(vault, path)
    rel = _posix_rel(vault, target)
    for prefix in _FORBIDDEN_PREFIXES:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            raise RetentionError(f"refusing delete under forbidden prefix: {rel}")
    allowed = (
        rel.startswith("sources/agent-events/")
        or rel.startswith("receipts/agent-events/")
    )
    if not allowed:
        raise RetentionError(f"refusing delete outside retention roots: {rel}")
    return target


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            if file_path.is_symlink():
                continue
            try:
                total += file_path.stat().st_size
            except OSError as exc:
                raise RetentionError(f"unreadable retention candidate: {file_path}") from exc
    return total


def _safe_component(value: str, *, label: str) -> str:
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise RetentionError(f"unsafe {label}: {value!r}")
    if PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        raise RetentionError(f"unsafe {label}: {value!r}")
    return value


def default_policy(
    *,
    max_packages: int = DEFAULT_MAX_PACKAGES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Return a schema-valid retention policy object."""
    if max_packages < 1:
        raise RetentionError("max_packages must be >= 1")
    if max_bytes < 1024:
        raise RetentionError("max_bytes must be >= 1024")
    policy = {
        "schema_version": 1,
        "schema": "atlas.event_retention.policy.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "RAW PACKAGE / RECEIPT RETENTION ≠ PROJECT AUTHORITY",
        "max_packages": max_packages,
        "max_bytes": max_bytes,
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(policy, POLICY_SCHEMA)
    return policy


def load_policy(
    vault: Path,
    *,
    max_packages: int | None = None,
    max_bytes: int | None = None,
    require_file: bool = False,
) -> dict[str, Any] | None:
    """Load vault retention policy; fail closed on malformed content.

    Returns ``None`` when no policy file exists and no explicit caps were
    supplied (caller should no-op). Explicit CLI/API caps synthesize a policy.
    """
    vault = vault.expanduser().resolve()
    path = _inside(vault, vault / POLICY_RELATIVE)
    raw: dict[str, Any] | None = None
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RetentionError(f"malformed retention policy: {exc}") from exc
        if not isinstance(loaded, dict):
            raise RetentionError("retention policy must be a JSON object")
        raw = loaded
    elif require_file:
        raise RetentionError(f"retention policy missing: {POLICY_RELATIVE.as_posix()}")

    if raw is None:
        if max_packages is None and max_bytes is None:
            return None
        return default_policy(
            max_packages=max_packages if max_packages is not None else DEFAULT_MAX_PACKAGES,
            max_bytes=max_bytes if max_bytes is not None else DEFAULT_MAX_BYTES,
        )

    # Fill defaults before schema validation; reject unknown/malformed fields.
    raw.setdefault("schema_version", 1)
    raw.setdefault("schema", "atlas.event_retention.policy.v1")
    raw.setdefault("truth_plane", "operational")
    raw.setdefault("authority_plane", "none")
    raw.setdefault(
        "note", "RAW PACKAGE / RECEIPT RETENTION ≠ PROJECT AUTHORITY"
    )
    raw.setdefault("generated", {"by": GENERATOR_ID})
    if max_packages is not None:
        raw["max_packages"] = max_packages
    if max_bytes is not None:
        raw["max_bytes"] = max_bytes
    try:
        validate_record(raw, POLICY_SCHEMA)
    except Exception as exc:
        raise RetentionError(f"malformed retention policy: {exc}") from exc
    if int(raw["max_packages"]) < 1:
        raise RetentionError("max_packages must be >= 1")
    if int(raw["max_bytes"]) < 1024:
        raise RetentionError("max_bytes must be >= 1024")
    return raw


def inventory_units(vault: Path) -> list[RetentionUnit]:
    """Inventory retainable package/receipt units under the two allowed roots."""
    vault = vault.expanduser().resolve()
    packages_root = _inside(vault, vault / RAW_PACKAGES_ROOT)
    receipts_root = _inside(vault, vault / RECEIPTS_ROOT)
    units: dict[str, RetentionUnit] = {}

    if packages_root.is_dir():
        for project_dir in sorted(packages_root.iterdir(), key=lambda p: p.name):
            if not project_dir.is_dir() or project_dir.is_symlink():
                continue
            project_id = _safe_component(project_dir.name, label="project_id")
            for event_dir in sorted(project_dir.iterdir(), key=lambda p: p.name):
                if not event_dir.is_dir() or event_dir.is_symlink():
                    continue
                event_id = _safe_component(event_dir.name, label="event_id")
                key = f"{project_id}/{event_id}"
                size = _dir_size(event_dir)
                receipt = receipts_root / project_id / f"{event_id}.yaml"
                receipt_path = receipt if receipt.is_file() and not receipt.is_symlink() else None
                if receipt_path is not None:
                    size += receipt_path.stat().st_size
                units[key] = RetentionUnit(
                    project_id=project_id,
                    event_id=event_id,
                    package_dir=event_dir,
                    receipt_path=receipt_path,
                    size_bytes=size,
                )

    if receipts_root.is_dir():
        for project_dir in sorted(receipts_root.iterdir(), key=lambda p: p.name):
            if not project_dir.is_dir() or project_dir.is_symlink():
                continue
            project_id = _safe_component(project_dir.name, label="project_id")
            for receipt in sorted(project_dir.iterdir(), key=lambda p: p.name):
                if not receipt.is_file() or receipt.is_symlink():
                    continue
                if not receipt.name.endswith(".yaml"):
                    continue
                event_id = _safe_component(receipt.name[: -len(".yaml")], label="event_id")
                key = f"{project_id}/{event_id}"
                if key in units:
                    continue
                units[key] = RetentionUnit(
                    project_id=project_id,
                    event_id=event_id,
                    package_dir=None,
                    receipt_path=receipt,
                    size_bytes=receipt.stat().st_size,
                )

    return [units[key] for key in sorted(units)]


def _select_victims(
    units: list[RetentionUnit],
    *,
    max_packages: int,
    max_bytes: int,
) -> tuple[list[RetentionUnit], list[RetentionUnit]]:
    """Return (kept, removed). Keep lexicographic tail under count/size caps."""
    kept = list(units)
    if len(kept) > max_packages:
        kept = kept[-max_packages:]
    while kept:
        total = sum(unit.size_bytes for unit in kept)
        if total <= max_bytes:
            break
        kept = kept[1:]
    kept_keys = {unit.unit_key for unit in kept}
    removed = [unit for unit in units if unit.unit_key not in kept_keys]
    return kept, removed


def _delete_unit(vault: Path, unit: RetentionUnit) -> list[str]:
    deleted: list[str] = []
    if unit.package_dir is not None and unit.package_dir.exists():
        target = _assert_allowed_delete(vault, unit.package_dir)
        if target.is_symlink() or not target.is_dir():
            raise RetentionError(f"refusing non-directory package delete: {target}")
        # Defence in depth: every child must remain under allowed roots.
        for root, _dirs, files in os.walk(target):
            for name in files:
                _assert_allowed_delete(vault, Path(root) / name)
        shutil.rmtree(target)
        deleted.append(_posix_rel(vault, target))
        parent = target.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    if unit.receipt_path is not None and unit.receipt_path.exists():
        target = _assert_allowed_delete(vault, unit.receipt_path)
        if target.is_symlink() or not target.is_file():
            raise RetentionError(f"refusing non-file receipt delete: {target}")
        target.unlink()
        deleted.append(_posix_rel(vault, target))
        parent = target.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    return deleted


def build_report(
    *,
    policy: dict[str, Any] | None,
    units_before: int,
    bytes_before: int,
    kept: list[RetentionUnit],
    removed: list[RetentionUnit],
    deleted_paths: list[str],
    applied: bool,
    dry_run: bool,
    status: Literal["applied", "dry-run", "no-op", "skipped-no-policy"],
) -> dict[str, Any]:
    report = {
        "schema_version": 1,
        "schema": "atlas.event_retention.report.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "RAW PACKAGE / RECEIPT RETENTION ≠ PROJECT AUTHORITY",
        "status": status,
        "applied": applied,
        "dry_run": dry_run,
        "policy": {
            "max_packages": policy["max_packages"] if policy else None,
            "max_bytes": policy["max_bytes"] if policy else None,
        },
        "counts": {
            "units_before": units_before,
            "units_kept": len(kept),
            "units_removed": len(removed),
            "bytes_before": bytes_before,
            "bytes_kept": sum(unit.size_bytes for unit in kept),
            "bytes_removed": sum(unit.size_bytes for unit in removed),
        },
        "removed_units": sorted(unit.unit_key for unit in removed),
        "deleted_paths": sorted(deleted_paths),
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(report, REPORT_SCHEMA)
    return report


def write_report(vault: Path, report: dict[str, Any]) -> Path:
    vault = vault.expanduser().resolve()
    validate_record(report, REPORT_SCHEMA)
    target = _inside(vault, vault / REPORT_RELATIVE)
    # Report lives under generated/ops only — never under Layer B / quarantine.
    rel = _posix_rel(vault, target)
    if not rel.startswith("generated/ops/"):
        raise RetentionError(f"refusing non-ops report path: {rel}")
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    _write_atomic(target, payload.encode("utf-8"))
    return target


def apply_event_retention(
    vault: Path,
    *,
    max_packages: int | None = None,
    max_bytes: int | None = None,
    dry_run: bool = False,
    require_policy_file: bool = False,
) -> dict[str, Any]:
    """Apply deterministic retention; emit report under ``generated/ops/``.

    When no policy file and no explicit caps exist, writes a skipped no-op
    report and deletes nothing.
    """
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise RetentionError(f"vault is not a directory: {vault}")

    policy = load_policy(
        vault,
        max_packages=max_packages,
        max_bytes=max_bytes,
        require_file=require_policy_file,
    )
    units = inventory_units(vault)
    bytes_before = sum(unit.size_bytes for unit in units)

    if policy is None:
        report = build_report(
            policy=None,
            units_before=len(units),
            bytes_before=bytes_before,
            kept=units,
            removed=[],
            deleted_paths=[],
            applied=False,
            dry_run=dry_run,
            status="skipped-no-policy",
        )
        write_report(vault, report)
        return report

    kept, removed = _select_victims(
        units,
        max_packages=int(policy["max_packages"]),
        max_bytes=int(policy["max_bytes"]),
    )
    deleted_paths: list[str] = []
    if dry_run:
        deleted_paths = []
        status: Literal["applied", "dry-run", "no-op", "skipped-no-policy"] = "dry-run"
        applied = False
    elif not removed:
        status = "no-op"
        applied = False
    else:
        for unit in removed:
            deleted_paths.extend(_delete_unit(vault, unit))
        status = "applied"
        applied = True

    report = build_report(
        policy=policy,
        units_before=len(units),
        bytes_before=bytes_before,
        kept=kept,
        removed=removed,
        deleted_paths=deleted_paths,
        applied=applied,
        dry_run=dry_run,
        status=status,
    )
    write_report(vault, report)
    return report


def maybe_apply_after_ingest(vault: Path) -> dict[str, Any] | None:
    """Thin ingest hook: apply only when a vault policy file is present.

    Missing policy → silent skip (ingestion must not invent retention).
    Malformed policy → raise (fail closed).
    """
    vault = vault.expanduser().resolve()
    policy_path = _inside(vault, vault / POLICY_RELATIVE)
    if not policy_path.is_file():
        return None
    return apply_event_retention(vault)
