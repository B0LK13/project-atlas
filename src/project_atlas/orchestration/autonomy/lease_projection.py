"""AS-ORCH-DURABLE-LEASE-PROJECTION-001 — durable read projection of leases.

PRIMARY_GOVERNOR remains the grant/ack source. This file is visibility
and recovery evidence only.

DURABLE_PROJECTION_IS_AUTHORITY = NO
LEASE_GRANT_SOURCE = PRIMARY_GOVERNOR
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.autonomy.models import AgentLease, NodeState
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

PACKAGE_ID: Final[Literal["AS-ORCH-DURABLE-LEASE-PROJECTION-001"]] = (
    "AS-ORCH-DURABLE-LEASE-PROJECTION-001"
)
PROJECTION_NAME: Final[str] = "leases.json"
LOCK_NAME: Final[str] = "leases.lock"
RELATIVE_DEFAULT: Final[Path] = Path(".atlas") / "orchestration" / "autonomy"


class ProjectionError(ValueError):
    code = "LEASE_PROJECTION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ProjectedLease(BaseModel):
    """Durable row. Not a grant. Sequence is logical, not wall-clock authority."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    package_id: str = Field(min_length=1, max_length=128)
    branch: str = Field(min_length=1, max_length=256)
    worktree: str = Field(min_length=1, max_length=256)
    base_pin: str = Field(min_length=40, max_length=40)
    authorized_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    forbidden_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    capabilities: tuple[str, ...] = Field(default_factory=tuple, max_length=8)
    start_state: NodeState
    status: Literal["ACTIVE", "RELEASED"]
    created_sequence: int = Field(ge=1, le=1_000_000)
    released_sequence: int | None = Field(default=None, ge=1, le=1_000_000)
    projection_is_authority: Literal[False] = False

    @field_validator("base_pin")
    @classmethod
    def _pin(cls, value: str) -> str:
        if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("base_pin must be a 40-char lowercase git SHA")
        return value


class ProjectionHonesty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_is_authority: Literal[False] = False
    grant_source: Literal["PRIMARY_GOVERNOR"] = "PRIMARY_GOVERNOR"
    ack_source: Literal["PRIMARY_GOVERNOR"] = "PRIMARY_GOVERNOR"
    wall_clock_is_authority: Literal[False] = False


class LeaseProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package: Literal["AS-ORCH-DURABLE-LEASE-PROJECTION-001"] = PACKAGE_ID
    honesty: ProjectionHonesty = Field(default_factory=ProjectionHonesty)
    leases: tuple[ProjectedLease, ...] = Field(default_factory=tuple, max_length=256)


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _store_file(store: Path) -> Path:
    root = store.expanduser().resolve()
    if ".." in Path(PROJECTION_NAME).parts:
        raise ProjectionError("projection path is unsafe", code="PATH_UNSAFE")
    target = (root / PROJECTION_NAME).resolve()
    if not _inside(root, target):
        raise ProjectionError("projection path escapes store", code="PATH_UNSAFE")
    return target


def _write_atomic(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(tmp, target)


def load_projection(store: Path) -> LeaseProjection:
    path = _store_file(store)
    if not path.is_file():
        return LeaseProjection()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectionError("projection is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(raw, dict):
        raise ProjectionError("projection is schema-invalid", code="STATE_CORRUPT")
    try:
        return LeaseProjection.model_validate(raw)
    except Exception as exc:
        raise ProjectionError("projection is schema-invalid", code="STATE_CORRUPT") from exc


def persist_projection(store: Path, projection: LeaseProjection) -> LeaseProjection:
    return _mutate_projection(store, lambda _current: projection)


def _mutate_projection(
    store: Path,
    mutator: Callable[[LeaseProjection], LeaseProjection],
) -> LeaseProjection:
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise ProjectionError("lock path escapes store", code="PATH_UNSAFE")
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            updated = mutator(load_projection(store))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise ProjectionError("projection lock is held", code="CONCURRENT_PROJECTION") from exc
    return updated


def _row_from_lease(lease: AgentLease, *, status: Literal["ACTIVE", "RELEASED"]) -> ProjectedLease:
    return ProjectedLease(
        lease_id=lease.lease_id,
        agent_id=lease.agent_id,
        package_id=lease.package_id,
        branch=lease.branch,
        worktree=lease.worktree,
        base_pin=lease.base_pin,
        authorized_paths=lease.authorized_paths,
        forbidden_paths=lease.forbidden_paths,
        capabilities=tuple(item.value for item in lease.capabilities),
        start_state=lease.start_state,
        status=status,
        created_sequence=lease.sequence,
        released_sequence=None if status == "ACTIVE" else lease.sequence,
        projection_is_authority=False,
    )


def active_rows(projection: LeaseProjection) -> tuple[ProjectedLease, ...]:
    return tuple(row for row in projection.leases if row.status == "ACTIVE")


def reject_stale_base(*, row: ProjectedLease, live_main: str) -> None:
    if row.base_pin != live_main:
        raise ProjectionError("stale lease base_pin rejected", code="STALE_LEASE")


def reject_foreign_worker(*, row: ProjectedLease, agent_id: str) -> None:
    if row.agent_id != agent_id:
        raise ProjectionError("foreign worker rejected", code="FOREIGN_WORKER")


def reject_foreign_package(*, row: ProjectedLease, package_id: str) -> None:
    if row.package_id != package_id:
        raise ProjectionError("foreign package rejected", code="FOREIGN_PACKAGE")


def project_grant(store: Path, lease: AgentLease, *, live_main: str) -> LeaseProjection:
    """Project a governor-issued grant. Does not itself grant authority."""
    if lease.base_pin != live_main:
        raise ProjectionError("stale lease base_pin rejected", code="STALE_LEASE")

    def _apply(current: LeaseProjection) -> LeaseProjection:
        for row in active_rows(current):
            if row.lease_id == lease.lease_id:
                if (
                    row.agent_id == lease.agent_id
                    and row.package_id == lease.package_id
                    and row.base_pin == lease.base_pin
                ):
                    return current
                raise ProjectionError("lease replay is forbidden", code="LEASE_REPLAY")
            if row.package_id == lease.package_id:
                raise ProjectionError(
                    "duplicate active lease for package",
                    code="DUPLICATE_ACTIVE_LEASE",
                )
            if row.agent_id == lease.agent_id:
                raise ProjectionError(
                    "worker already holds an active lease",
                    code="FOREIGN_WORKER",
                )
        return LeaseProjection(leases=(*current.leases, _row_from_lease(lease, status="ACTIVE")))

    return _mutate_projection(store, _apply)


def project_release(store: Path, lease: AgentLease, *, live_main: str) -> LeaseProjection:
    def _apply(current: LeaseProjection) -> LeaseProjection:
        rows: list[ProjectedLease] = []
        found = False
        for row in current.leases:
            if row.lease_id != lease.lease_id:
                rows.append(row)
                continue
            found = True
            reject_foreign_worker(row=row, agent_id=lease.agent_id)
            reject_foreign_package(row=row, package_id=lease.package_id)
            reject_stale_base(row=row, live_main=live_main)
            rows.append(
                row.model_copy(
                    update={"status": "RELEASED", "released_sequence": lease.sequence}
                )
            )
        if not found:
            raise ProjectionError("lease not in projection", code="LEASE_UNKNOWN")
        return LeaseProjection(leases=tuple(rows))

    return _mutate_projection(store, _apply)


def visible_active_lease(
    store: Path,
    *,
    lease_id: str,
    agent_id: str,
    package_id: str,
    live_main: str,
) -> ProjectedLease:
    """Read-only ack/visibility. Projection is not a grant."""
    for row in active_rows(load_projection(store)):
        if row.lease_id != lease_id:
            continue
        reject_foreign_worker(row=row, agent_id=agent_id)
        reject_foreign_package(row=row, package_id=package_id)
        reject_stale_base(row=row, live_main=live_main)
        return row
    raise ProjectionError("active lease not visible", code="LEASE_NOT_VISIBLE")
