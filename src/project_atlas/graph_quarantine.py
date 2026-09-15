"""AS-GRAPH-004 — Durable graph quarantine store / health / incremental.

Consumes AS-GRAPH-003 soft ``RelationshipQuarantine`` candidates into a Core-owned
durable quarantine store under ``generated/graph/quarantine/**``, emits
deterministic health counters under ``generated/graph/health/**``, tracks
incremental input hashes under ``generated/graph/incremental/**``, and writes
immutable refresh receipts under ``generated/graph/quarantine/**``.

Never last-write-wins quarantine into retained relationships. Never elevates
quarantine to domain authority / claims / temporal / CP ``relationships/``.
Never invents Core claim conflicts. No wall-clock timestamps in generated
content (NFR-001).

Truth boundary: GRAPH QUARANTINE ≠ AUTOMATIC AUTHORITY.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from project_atlas.graph_relationships import (
    RelationshipQuarantine,
    RelationshipStoreResult,
)
from project_atlas.schema import validate_record

PACKAGE_ID = "AS-GRAPH-004"
SOURCE_PACKAGE_ID = "AS-GRAPH-003"
AUTHORITY_LEVEL = "derived"
TRUTH_BOUNDARY = "GRAPH QUARANTINE ≠ AUTOMATIC AUTHORITY"
GENERATED_BY = "atlas-graph-004"

HealthState = Literal["healthy", "degraded", "unhealthy", "unknown"]

# Deterministic rollup thresholds (metadata counters only — not trust scores).
_DEGRADED_MAX_QUARANTINE = 10

ALLOWED_WRITE_PREFIXES: tuple[str, ...] = (
    "generated/graph/quarantine/",
    "generated/graph/health/",
    "generated/graph/incremental/",
)

_FORBIDDEN_WRITE_PREFIXES: tuple[str, ...] = (
    "relationships/",
    "state/current-state/",
    "state/authoritative-state/",
    "state/global-entities/",
    "claims/",
    "generated/indexes/",
    "generated/query/",
    "generated/graph/resolved/",
    "generated/graph/quarantine-candidates/",
    "generated/graph/acceptance/",
    "generated/graph/relationships/",
    "generated/graph/relationship-quarantine/",
    "generated/ops/",
)

_REMEDIATION: dict[str, str] = {
    "orphaned-endpoint": (
        "Resolve missing endpoint via AS-GRAPH-002 mapping or source artifact, "
        "then re-run store-graph."
    ),
    "quarantined-endpoint": (
        "Clear endpoint quarantine (ambiguous/unresolved identity) before "
        "retaining the edge."
    ),
    "cross-project-endpoint": (
        "Cross-project edges are forbidden in project-local store; route via "
        "AS-XPROJ when certified, never promote here."
    ),
    "incompatible-duplicate": (
        "Review incompatible duplicate fingerprints; no autonomous LWW — "
        "choose remediation manually and re-ingest."
    ),
    "capacity-rejected": (
        "Reduce edge batch size below capacity limit and re-run; never accept "
        "silent subset success."
    ),
    "malformed-edge": (
        "Fix malformed Graphify edge payload (type/endpoints/schema) and re-run "
        "acceptance/store."
    ),
}

# Test seam for injected mid-promote failure (leaves prior state intact).
_replace_path = os.replace


class GraphQuarantineError(ValueError):
    """Fail-closed durable quarantine / health / incremental error."""


@dataclass(frozen=True)
class DurableQuarantineRecord:
    """Durable quarantine record — never authority; never LWW-promoted."""

    project_id: str
    quarantine_id: str
    category: str
    reason: str
    source_candidate_id: str
    content_hash: str
    remediation: str
    relationship_fingerprint: str | None = None
    graphify_edge_ids: tuple[str, ...] = ()
    source_graphify_id: str | None = None
    target_graphify_id: str | None = None
    artifact_refs: tuple[dict[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "project_id": self.project_id,
            "quarantine_id": self.quarantine_id,
            "category": self.category,
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": (
                    "Durable quarantine is derived-only; "
                    "never promote to authority or retained relationships."
                ),
            },
            "status": "quarantined",
            "reason": self.reason,
            "remediation": self.remediation,
            "source_package_id": SOURCE_PACKAGE_ID,
            "source_candidate_id": self.source_candidate_id,
            "content_hash": self.content_hash,
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATED_BY},
        }
        if self.relationship_fingerprint is not None:
            payload["relationship_fingerprint"] = self.relationship_fingerprint
        if self.graphify_edge_ids:
            payload["graphify_edge_ids"] = list(self.graphify_edge_ids)
        if self.source_graphify_id is not None:
            payload["source_graphify_id"] = self.source_graphify_id
        if self.target_graphify_id is not None:
            payload["target_graphify_id"] = self.target_graphify_id
        if self.artifact_refs:
            payload["artifact_refs"] = [dict(item) for item in self.artifact_refs]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GraphHealthSnapshot:
    """Deterministic graph health counters (operational; not authority)."""

    project_id: str
    retained_count: int
    quarantined_count: int
    category_counts: dict[str, int]
    link_quality_histogram: dict[str, int]
    health_state: HealthState
    input_content_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "project_id": self.project_id,
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": "Graph health counters are operational metadata ≠ domain authority.",
            },
            "truth_plane": "operational",
            "authority_plane": "none",
            "note": "GRAPH HEALTH ≠ PROJECT AUTHORITY",
            "retained_count": self.retained_count,
            "quarantined_count": self.quarantined_count,
            "category_counts": dict(sorted(self.category_counts.items())),
            "link_quality_histogram": dict(sorted(self.link_quality_histogram.items())),
            "health_state": self.health_state,
            "input_content_hash": self.input_content_hash,
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATED_BY},
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GraphIncrementalState:
    """Incremental hash/state for deterministic quarantine refresh."""

    project_id: str
    input_content_hash: str
    quarantine_store_hash: str
    health_hash: str
    quarantine_ids: tuple[str, ...]
    refreshed: bool
    removed_artifact_retention: str = "deferred-explicit"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "project_id": self.project_id,
            "authority": {
                "level": AUTHORITY_LEVEL,
                "note": "Incremental state is derived operational metadata ≠ authority.",
            },
            "input_content_hash": self.input_content_hash,
            "quarantine_store_hash": self.quarantine_store_hash,
            "health_hash": self.health_hash,
            "quarantine_ids": list(self.quarantine_ids),
            "refreshed": self.refreshed,
            "removed_artifact_retention": self.removed_artifact_retention,
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATED_BY},
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GraphQuarantineReceipt:
    """Immutable quarantine-refresh receipt (derived; never canonical override)."""

    project_id: str
    receipt_id: str
    input_content_hash: str
    quarantined_count: int
    retained_count: int
    health_state: HealthState
    refreshed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "receipt_type": "atlas-graph-quarantine-refresh",
            "receipt_id": self.receipt_id,
            "project_id": self.project_id,
            "authority": {
                "graphify": "derived",
                "level": AUTHORITY_LEVEL,
                "canonical_override_allowed": False,
                "note": "Quarantine receipt is derived-only; never elevates authority.",
            },
            "input_content_hash": self.input_content_hash,
            "quarantined_count": self.quarantined_count,
            "retained_count": self.retained_count,
            "health_state": self.health_state,
            "refreshed": self.refreshed,
            "truth_boundary": TRUTH_BOUNDARY,
            "generated": {"by": GENERATED_BY},
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class QuarantineStoreResult:
    """Batch durable quarantine + health + incremental + receipt output."""

    project_id: str
    records: tuple[DurableQuarantineRecord, ...]
    health: GraphHealthSnapshot
    incremental: GraphIncrementalState
    receipt: GraphQuarantineReceipt

    @property
    def quarantined_count(self) -> int:
        return len(self.records)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "project_id": self.project_id,
            "authority": {"level": AUTHORITY_LEVEL},
            "quarantined_count": self.quarantined_count,
            "records": [item.as_dict() for item in self.records],
            "health": self.health.as_dict(),
            "incremental": self.incremental.as_dict(),
            "receipt": self.receipt.as_dict(),
            "truth_boundary": TRUTH_BOUNDARY,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class _PromotionEntry:
    path: Path
    staged: Path
    backup: Path
    had_original: bool


def _canonical_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_name(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", token).strip("-")
    return cleaned or "quarantine"


def _redact_reason(reason: str) -> str:
    """Never echo secret-shaped content in durable quarantine reasons."""
    text = reason.strip()
    lowered = text.lower()
    for needle in ("password=", "secret=", "token=", "api_key=", "bearer ", "private-key"):
        if needle in lowered:
            return "redacted-sensitive-reason"
    return text[:240]


def _remediation_for(category: str) -> str:
    return _REMEDIATION.get(
        category,
        "Review quarantine category, remediate source/mapping, and re-run graph store.",
    )


def _assert_project_id(project_id: str) -> None:
    if not project_id or "/" in project_id or "\\" in project_id or project_id in {".", ".."}:
        raise GraphQuarantineError("project-id-unsafe")


def compute_input_content_hash(store_result: RelationshipStoreResult) -> str:
    """Deterministic hash of GRAPH-003 store inputs relevant to quarantine refresh."""
    payload = {
        "project_id": store_result.project_id,
        "retained_fingerprints": sorted(
            item.relationship_fingerprint for item in store_result.relationships
        ),
        "retained_count": store_result.retained_count,
        "link_quality_histogram": dict(sorted(store_result.link_quality_histogram.items())),
        "quarantine": [item.as_dict() for item in store_result.quarantine],
        "errors": list(store_result.errors),
    }
    return _canonical_digest(payload)


def _quarantine_id(candidate: RelationshipQuarantine) -> str:
    """Stable durable id derived from project + candidate identity + content."""
    basis = {
        "project_id": candidate.project_id,
        "candidate_id": candidate.candidate_id,
        "category": candidate.category,
        "relationship_fingerprint": candidate.relationship_fingerprint,
        "graphify_edge_ids": list(candidate.graphify_edge_ids),
    }
    digest = _canonical_digest(basis)
    return f"gq-{_safe_name(candidate.candidate_id)}-{digest[:16]}"


def _candidate_content_hash(candidate: RelationshipQuarantine) -> str:
    return _canonical_digest(candidate.as_dict())


def _receipt_id(*, project_id: str, input_content_hash: str) -> str:
    digest = _canonical_digest({"project_id": project_id, "input_content_hash": input_content_hash})
    return f"gqr-{digest[:24]}"


def derive_health_state(*, retained_count: int, quarantined_count: int) -> HealthState:
    """Deterministic rollup — counters only; Unknown ≠ healthy."""
    if retained_count < 0 or quarantined_count < 0:
        return "unknown"
    if quarantined_count == 0:
        return "healthy"
    if quarantined_count <= _DEGRADED_MAX_QUARANTINE:
        return "degraded"
    return "unhealthy"


def materialize_from_candidates(
    candidates: Sequence[RelationshipQuarantine],
    *,
    project_id: str,
    retained_count: int = 0,
    link_quality_histogram: Mapping[str, int] | None = None,
    errors: Sequence[Mapping[str, str]] = (),
    prior_state: GraphIncrementalState | Mapping[str, Any] | None = None,
) -> QuarantineStoreResult:
    """Materialize durable quarantine + health + incremental from soft candidates."""
    _assert_project_id(project_id)
    histogram = dict(sorted((link_quality_histogram or {}).items()))
    ordered = sorted(candidates, key=lambda item: item.candidate_id.casefold())
    for candidate in ordered:
        if candidate.project_id != project_id:
            raise GraphQuarantineError("project-id-mismatch")

    soft_payload = {
        "project_id": project_id,
        "retained_fingerprints": [],
        "retained_count": retained_count,
        "link_quality_histogram": histogram,
        "quarantine": [item.as_dict() for item in ordered],
        "errors": [dict(item) for item in errors],
    }
    input_hash = _canonical_digest(soft_payload)
    prior = _coerce_prior_state(prior_state)
    records = tuple(_durable_from_candidate(item) for item in ordered)
    return _assemble_result(
        project_id=project_id,
        retained_count=retained_count,
        records=records,
        histogram=histogram,
        input_hash=input_hash,
        prior=prior,
    )


def materialize_quarantine_store(
    store_result: RelationshipStoreResult,
    *,
    prior_state: GraphIncrementalState | Mapping[str, Any] | None = None,
) -> QuarantineStoreResult:
    """Consume GRAPH-003 ``RelationshipStoreResult`` into durable quarantine artifacts."""
    _assert_project_id(store_result.project_id)
    input_hash = compute_input_content_hash(store_result)
    prior = _coerce_prior_state(prior_state)
    ordered = sorted(store_result.quarantine, key=lambda item: item.candidate_id.casefold())
    for candidate in ordered:
        if candidate.project_id != store_result.project_id:
            raise GraphQuarantineError("project-id-mismatch")

    records = tuple(_durable_from_candidate(item) for item in ordered)
    return _assemble_result(
        project_id=store_result.project_id,
        retained_count=store_result.retained_count,
        records=records,
        histogram=dict(sorted(store_result.link_quality_histogram.items())),
        input_hash=input_hash,
        prior=prior,
    )


def _assemble_result(
    *,
    project_id: str,
    retained_count: int,
    records: tuple[DurableQuarantineRecord, ...],
    histogram: Mapping[str, int],
    input_hash: str,
    prior: GraphIncrementalState | None,
) -> QuarantineStoreResult:
    health = _build_health(
        project_id=project_id,
        retained_count=retained_count,
        records=records,
        histogram=histogram,
        input_content_hash=input_hash,
    )
    store_hash = _canonical_digest([item.as_dict() for item in records])
    health_hash = _canonical_digest(health.as_dict())
    refreshed = not (prior is not None and prior.input_content_hash == input_hash)
    incremental = GraphIncrementalState(
        project_id=project_id,
        input_content_hash=input_hash,
        quarantine_store_hash=store_hash,
        health_hash=health_hash,
        quarantine_ids=tuple(item.quarantine_id for item in records),
        refreshed=refreshed,
    )
    receipt = GraphQuarantineReceipt(
        project_id=project_id,
        receipt_id=_receipt_id(project_id=project_id, input_content_hash=input_hash),
        input_content_hash=input_hash,
        quarantined_count=len(records),
        retained_count=retained_count,
        health_state=health.health_state,
        refreshed=refreshed,
    )
    return QuarantineStoreResult(
        project_id=project_id,
        records=records,
        health=health,
        incremental=incremental,
        receipt=receipt,
    )


def _durable_from_candidate(candidate: RelationshipQuarantine) -> DurableQuarantineRecord:
    refs = tuple(
        {"relative_path": ref.relative_path, "sha256": ref.sha256}
        for ref in candidate.artifact_refs
    )
    return DurableQuarantineRecord(
        project_id=candidate.project_id,
        quarantine_id=_quarantine_id(candidate),
        category=candidate.category,
        reason=_redact_reason(candidate.reason),
        remediation=_remediation_for(candidate.category),
        source_candidate_id=candidate.candidate_id,
        content_hash=_candidate_content_hash(candidate),
        relationship_fingerprint=candidate.relationship_fingerprint,
        graphify_edge_ids=tuple(candidate.graphify_edge_ids),
        source_graphify_id=candidate.source_graphify_id,
        target_graphify_id=candidate.target_graphify_id,
        artifact_refs=refs,
    )


def _build_health(
    *,
    project_id: str,
    retained_count: int,
    records: Sequence[DurableQuarantineRecord],
    histogram: Mapping[str, int],
    input_content_hash: str,
) -> GraphHealthSnapshot:
    categories: dict[str, int] = {}
    for item in records:
        categories[item.category] = categories.get(item.category, 0) + 1
    quarantined_count = len(records)
    return GraphHealthSnapshot(
        project_id=project_id,
        retained_count=retained_count,
        quarantined_count=quarantined_count,
        category_counts=dict(sorted(categories.items())),
        link_quality_histogram=dict(sorted(histogram.items())),
        health_state=derive_health_state(
            retained_count=retained_count,
            quarantined_count=quarantined_count,
        ),
        input_content_hash=input_content_hash,
    )


def _coerce_prior_state(
    prior_state: GraphIncrementalState | Mapping[str, Any] | None,
) -> GraphIncrementalState | None:
    if prior_state is None:
        return None
    if isinstance(prior_state, GraphIncrementalState):
        return prior_state
    try:
        return GraphIncrementalState(
            project_id=str(prior_state["project_id"]),
            input_content_hash=str(prior_state["input_content_hash"]),
            quarantine_store_hash=str(prior_state["quarantine_store_hash"]),
            health_hash=str(prior_state["health_hash"]),
            quarantine_ids=tuple(str(item) for item in prior_state.get("quarantine_ids", [])),
            refreshed=bool(prior_state.get("refreshed", False)),
            removed_artifact_retention=str(
                prior_state.get("removed_artifact_retention", "deferred-explicit")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GraphQuarantineError("malformed-prior-incremental-state") from exc


def load_incremental_state(vault: Path, *, project_id: str) -> GraphIncrementalState | None:
    """Load prior incremental state if present; None when absent."""
    _assert_project_id(project_id)
    relative = f"generated/graph/incremental/{project_id}/state.json"
    path = vault.expanduser().resolve() / relative
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GraphQuarantineError("malformed-incremental-state") from exc
    if not isinstance(payload, Mapping):
        raise GraphQuarantineError("malformed-incremental-state")
    return _coerce_prior_state(payload)


def inspect_quarantine_store(result: QuarantineStoreResult) -> dict[str, Any]:
    """Library observability: counts and health; no secret payloads."""
    return {
        "package_id": PACKAGE_ID,
        "project_id": result.project_id,
        "authority": AUTHORITY_LEVEL,
        "quarantined_count": result.quarantined_count,
        "health_state": result.health.health_state,
        "category_counts": dict(sorted(result.health.category_counts.items())),
        "input_content_hash": result.incremental.input_content_hash,
        "refreshed": result.incremental.refreshed,
        "receipt_id": result.receipt.receipt_id,
        "truth_boundary": TRUTH_BOUNDARY,
    }


def promote_quarantine_to_authority_forbidden(
    record: DurableQuarantineRecord | Mapping[str, Any],
) -> None:
    """Fail-closed: durable quarantine must never elevate to authority."""
    _ = record
    raise GraphQuarantineError("quarantine-authority-elevation-forbidden")


def promote_quarantine_to_relationship_forbidden(
    record: DurableQuarantineRecord | Mapping[str, Any],
) -> None:
    """Fail-closed: durable quarantine must never LWW-promote into retained edges."""
    _ = record
    raise GraphQuarantineError("quarantine-relationship-promotion-forbidden")


def synthesize_claim_conflict_forbidden(
    record: DurableQuarantineRecord | Mapping[str, Any],
) -> None:
    """Fail-closed: graph quarantine never invents Core claim conflicts."""
    _ = record
    raise GraphQuarantineError("claim-conflict-synthesis-forbidden")


def _safe_vault_relative(vault: Path, relative: str) -> Path:
    if relative.startswith(("/", "\\")) or "\\" in relative or ".." in Path(relative).parts:
        raise GraphQuarantineError(f"path-escape:{relative}")
    if not any(relative.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
        raise GraphQuarantineError(f"forbidden-write-prefix:{relative}")
    if any(relative.startswith(prefix) for prefix in _FORBIDDEN_WRITE_PREFIXES):
        raise GraphQuarantineError(f"forbidden-write-prefix:{relative}")
    root = vault.expanduser().resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise GraphQuarantineError(f"path-escape:{relative}")
    return candidate


def _promote(plan: dict[Path, bytes]) -> None:
    """Prepare → validate-staged → promote with rollback (failed promote leaves prior)."""
    transaction = uuid4().hex
    entries: list[_PromotionEntry] = []
    try:
        for path in sorted(plan):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not path.is_file():
                raise GraphQuarantineError(f"canonical-target-not-file:{path}")
            if path.is_file() and path.read_bytes() == plan[path]:
                continue
            staged = path.with_name(f".{path.name}.{transaction}.atlas-stage")
            backup = path.with_name(f".{path.name}.{transaction}.atlas-backup")
            staged.write_bytes(plan[path])
            entries.append(
                _PromotionEntry(
                    path=path,
                    staged=staged,
                    backup=backup,
                    had_original=path.exists(),
                )
            )
    except BaseException:
        for entry in entries:
            entry.staged.unlink(missing_ok=True)
            entry.backup.unlink(missing_ok=True)
        raise

    touched: list[_PromotionEntry] = []
    try:
        for entry in entries:
            if entry.had_original:
                _replace_path(entry.path, entry.backup)
            touched.append(entry)
            _replace_path(entry.staged, entry.path)
    except BaseException as promotion_error:
        for entry in reversed(touched):
            with contextlib.suppress(OSError):
                if entry.had_original:
                    # Rollback always uses real os.replace so injected promote
                    # seams cannot strand a half-applied vault.
                    os.replace(entry.backup, entry.path)
                else:
                    entry.path.unlink(missing_ok=True)
        for entry in entries:
            with contextlib.suppress(OSError):
                entry.staged.unlink(missing_ok=True)
                entry.backup.unlink(missing_ok=True)
        raise GraphQuarantineError("promotion-failed-prior-state-intact") from promotion_error

    for entry in entries:
        entry.staged.unlink(missing_ok=True)
        entry.backup.unlink(missing_ok=True)


def write_quarantine_outputs(
    result: QuarantineStoreResult,
    *,
    vault: Path,
    skip_unchanged: bool = True,
    strict: bool = False,
) -> list[str]:
    """Deterministic vault emits under quarantine / health / incremental prefixes.

    Transaction ordering: prepare → validate → promote. Failed promote leaves
    prior state intact. When ``skip_unchanged`` is True and
    ``incremental.refreshed`` is False, returns planned relative paths without
    rewriting (incremental no-op).

    Strict mode fail-closes on incompatible-duplicate without writing success
    receipts.
    """
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise GraphQuarantineError(f"vault-missing:{vault}")

    project = result.project_id
    _assert_project_id(project)

    if strict and any(item.category == "incompatible-duplicate" for item in result.records):
        raise GraphQuarantineError("strict-conflict-fail-closed")

    planned: list[str] = []
    for record in result.records:
        safe = _safe_name(record.quarantine_id)
        planned.append(f"generated/graph/quarantine/{project}/{safe}.json")
    planned.append(f"generated/graph/quarantine/{project}/receipt.json")
    planned.append(f"generated/graph/health/{project}/health.json")
    planned.append(f"generated/graph/incremental/{project}/state.json")
    planned.sort()

    if skip_unchanged and not result.incremental.refreshed:
        return planned

    # prepare + validate (no canonical mutation yet)
    plan: dict[Path, bytes] = {}
    for record in result.records:
        safe = _safe_name(record.quarantine_id)
        relative = f"generated/graph/quarantine/{project}/{safe}.json"
        path = _safe_vault_relative(vault, relative)
        payload = record.as_dict()
        validate_record(payload, "graph-quarantine-record")
        plan[path] = record.to_json().encode("utf-8")

    receipt_relative = f"generated/graph/quarantine/{project}/receipt.json"
    receipt_path = _safe_vault_relative(vault, receipt_relative)
    validate_record(result.receipt.as_dict(), "graph-quarantine-receipt")
    plan[receipt_path] = result.receipt.to_json().encode("utf-8")

    health_relative = f"generated/graph/health/{project}/health.json"
    health_path = _safe_vault_relative(vault, health_relative)
    validate_record(result.health.as_dict(), "graph-health-snapshot")
    plan[health_path] = result.health.to_json().encode("utf-8")

    incr_relative = f"generated/graph/incremental/{project}/state.json"
    incr_path = _safe_vault_relative(vault, incr_relative)
    validate_record(result.incremental.as_dict(), "graph-incremental-state")
    plan[incr_path] = result.incremental.to_json().encode("utf-8")

    _promote(plan)
    return planned


def promote_quarantine_path_forbidden(relative: str) -> None:
    """Public helper for tests: assert a relative path is rejected by path policy."""
    _safe_vault_relative(Path("."), relative)


__all__ = [
    "ALLOWED_WRITE_PREFIXES",
    "AUTHORITY_LEVEL",
    "GENERATED_BY",
    "PACKAGE_ID",
    "SOURCE_PACKAGE_ID",
    "TRUTH_BOUNDARY",
    "DurableQuarantineRecord",
    "GraphHealthSnapshot",
    "GraphIncrementalState",
    "GraphQuarantineError",
    "GraphQuarantineReceipt",
    "QuarantineStoreResult",
    "compute_input_content_hash",
    "derive_health_state",
    "inspect_quarantine_store",
    "load_incremental_state",
    "materialize_from_candidates",
    "materialize_quarantine_store",
    "promote_quarantine_path_forbidden",
    "promote_quarantine_to_authority_forbidden",
    "promote_quarantine_to_relationship_forbidden",
    "synthesize_claim_conflict_forbidden",
    "write_quarantine_outputs",
]
