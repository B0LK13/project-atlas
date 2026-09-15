"""Durable package canonical route registry — single winner, generation-bound."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    SdkRuntimeError,
)

REGISTRY_NAME: Final[str] = "package-route.json"
CANONICAL_PR: Final[int] = 429
SUPERSEDED_PR: Final[int] = 428
CANONICAL_BRANCH: Final[str] = "feat/as-orch-continuation-broker-001"
TRUSTED_MAIN: Final[str] = "7e797468a2eca37c959920912b1fa264df4be638"


class PackageRouteRecord(BaseModel):
    """Authoritative package route. Not merge authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: str = PACKAGE_ID
    canonical_pr: int = CANONICAL_PR
    canonical_branch: str = CANONICAL_BRANCH
    canonical_head: str | None = None
    canonical_tree: str | None = None
    superseded_lineages: tuple[int, ...] = (SUPERSEDED_PR,)
    dag_generation: int = Field(default=0, ge=0, le=1_000_000)
    registry_revision: int = Field(default=0, ge=0, le=1_000_000)
    trusted_main: str = TRUSTED_MAIN
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def package_route_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / REGISTRY_NAME


def load_package_route(root: Path) -> PackageRouteRecord:
    path = package_route_path(root)
    if path.is_file():
        try:
            return PackageRouteRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return PackageRouteRecord()


def persist_package_route(root: Path, record: PackageRouteRecord) -> Path:
    path = package_route_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def update_package_route_on_head_move(
    root: Path,
    *,
    head: str,
    tree: str | None,
    dag_generation: int,
) -> PackageRouteRecord:
    """Atomic head/generation/revision advance before mutating dispatch."""
    current = load_package_route(root)
    if dag_generation < current.dag_generation:
        raise SdkRuntimeError(
            "package route generation rollback rejected",
            code="PACKAGE_ROUTE_ROLLBACK",
        )
    if (
        current.canonical_head == head
        and current.canonical_tree == tree
        and current.dag_generation == dag_generation
    ):
        return current
    updated = current.model_copy(
        update={
            "canonical_head": head,
            "canonical_tree": tree,
            "dag_generation": dag_generation,
            "registry_revision": current.registry_revision + 1,
            "canonical_pr": CANONICAL_PR,
            "canonical_branch": CANONICAL_BRANCH,
            "package_id": PACKAGE_ID,
        }
    )
    persist_package_route(root, updated)
    return updated


def require_mutating_route(
    root: Path,
    *,
    target_pr: int,
    branch: str,
    head: str | None,
    dag_generation: int,
) -> PackageRouteRecord:
    """Consult authoritative route before minting a mutating lease."""
    route = load_package_route(root)
    if target_pr in route.superseded_lineages or target_pr == SUPERSEDED_PR:
        raise SdkRuntimeError(
            "superseded PR mutation unauthorized (STALE_LINEAGE)",
            code="STALE_LINEAGE",
        )
    if target_pr != route.canonical_pr or target_pr != CANONICAL_PR:
        raise SdkRuntimeError("non-canonical PR mutation rejected", code="STALE_LINEAGE")
    if branch != route.canonical_branch:
        raise SdkRuntimeError("branch mismatch vs package route", code="STALE_LINEAGE")
    if route.canonical_head and head and head != route.canonical_head:
        raise SdkRuntimeError("stale head vs package route", code="STALE_LINEAGE")
    if dag_generation != route.dag_generation:
        raise SdkRuntimeError(
            "old dag generation is evidence-only",
            code="EVIDENCE_ONLY_GENERATION",
        )
    return route
