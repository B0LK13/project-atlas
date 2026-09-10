"""Adapters for task contracts and execution evidence.

When AS-TASK-CONTRACT-001 / execution-quality interfaces are not importable
from this checkout, callers supply explicitly labeled fixtures
(``source_kind=FIXTURE_LABELED``). Real loaders are used when present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.task_context.models import TaskContextError, sha256_text
from project_atlas.task_context.paths import read_text_under_root, resolve_source_file

SourceKind = Literal["LIVE_MODULE", "FIXTURE_LABELED", "FILE"]


class ContextSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=512)
    why: str = Field(min_length=1, max_length=512)
    digest: str | None = Field(default=None, max_length=128)
    tier_hint: Literal["mandatory", "evidence", "background"] = "evidence"


class ContractSnapshot(BaseModel):
    """Minimal portable contract shape for independent development.

    Compatible with AS-TASK-CONTRACT-001 field names used for selection.
    Does not grant execution authorization.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str
    contract_version: int = 1
    objective: str
    observable_outcome: str
    scope: tuple[str, ...]
    exclusions: tuple[str, ...] = ()
    mutation_paths: tuple[str, ...]
    repository: str
    base_pin: str
    candidate_identity: str | None = None
    policy_refs: tuple[str, ...] = ()
    context: tuple[ContextSourceRef, ...] = ()
    requirements: tuple[dict[str, Any], ...] = ()
    acceptance: tuple[dict[str, Any], ...] = ()
    depends_on: tuple[str, ...] = ()
    execution_authorized: Literal[False] = False
    interface_refs: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    source_kind: SourceKind = "FIXTURE_LABELED"

    @field_validator("mutation_paths", "scope")
    @classmethod
    def _non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise TaskContextError("scope/mutation_paths required", code="CONTRACT_INCOMPLETE")
        return value


class EvidenceRecord(BaseModel):
    """Structured execution evidence (FIXTURE_LABELED until quality-loop lands)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    action_id: str
    summary: str
    outcome: Literal["passed", "failed", "unknown", "blocked"]
    artifact_paths: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    check_results: tuple[dict[str, Any], ...] = ()
    #: Explicit: prose-only claims are not completion proof.
    completion_proven: bool = False
    source_kind: SourceKind = "FIXTURE_LABELED"


def contract_digest(snapshot: ContractSnapshot) -> str:
    payload = snapshot.model_dump(mode="json")
    payload.pop("source_kind", None)
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def load_contract_snapshot(path: Path) -> ContractSnapshot:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TaskContextError(f"cannot load contract: {exc}", code="CONTRACT_UNREADABLE") from exc
    if not isinstance(raw, dict):
        raise TaskContextError("contract must be a JSON object", code="CONTRACT_MALFORMED")
    raw.setdefault("source_kind", "FILE")
    try:
        return ContractSnapshot.model_validate(raw)
    except Exception as exc:
        raise TaskContextError(f"contract invalid: {exc}", code="CONTRACT_INVALID") from exc


def try_load_live_taskcontract(path: Path) -> ContractSnapshot | None:
    """Optional bridge to AS-TASK-CONTRACT-001 when the module exists.

    Returns None when the live module is absent **or** the file is not a
    TaskContract (e.g. a labeled ContractSnapshot fixture). Callers that
    require a live TaskContract must use an explicit live loader and fail
    closed — this helper never silently invents fields.
    """
    try:
        from project_atlas.orchestration.taskcontract.models import (  # type: ignore[import-not-found]
            TaskContract,
        )
    except ImportError:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # Heuristic: TaskContract requires package_id / source; snapshot fixtures do not.
    if data.get("package_id") != "AS-TASK-CONTRACT-001" and "source" not in data:
        return None
    try:
        contract = TaskContract.model_validate(data)
    except Exception:
        return None
    context = tuple(
        ContextSourceRef(
            source_id=item.source_id,
            path=item.path,
            why=item.why,
            digest=item.digest,
        )
        for item in contract.context
    )
    return ContractSnapshot(
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        objective=contract.objective,
        observable_outcome=contract.observable_outcome,
        scope=contract.scope,
        exclusions=contract.exclusions,
        mutation_paths=contract.mutation_paths,
        repository=contract.repository,
        base_pin=contract.base_pin,
        policy_refs=tuple(
            f"{ref.kind}:{ref.reference}" for ref in contract.authorization_references
        ),
        context=context,
        requirements=tuple(r.model_dump(mode="json") for r in contract.requirements),
        acceptance=tuple(a.model_dump(mode="json") for a in contract.acceptance),
        depends_on=contract.depends_on,
        source_kind="LIVE_MODULE",
    )


def load_contract(path: Path, *, prefer_live: bool = True) -> ContractSnapshot:
    if prefer_live:
        live = try_load_live_taskcontract(path)
        if live is not None:
            return live
    return load_contract_snapshot(path)


def load_evidence_bundle(path: Path) -> tuple[EvidenceRecord, ...]:
    if not path.exists():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TaskContextError(f"evidence unreadable: {exc}", code="EVIDENCE_UNREADABLE") from exc
    if isinstance(raw, dict) and "records" in raw:
        items = raw["records"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise TaskContextError("evidence must be list or {records:[]}", code="EVIDENCE_MALFORMED")
    out: list[EvidenceRecord] = []
    for item in items:
        out.append(EvidenceRecord.model_validate(item))
    return tuple(out)


def materialize_source(
    root: Path, ref: ContextSourceRef
) -> tuple[str, bytes, str | None]:
    """Read source bytes under root. Returns (text, bytes, missing_error)."""
    try:
        text, data = read_text_under_root(root, ref.path)
        return text, data, None
    except TaskContextError as exc:
        if exc.code in {
            "SOURCE_MISSING",
            "PATH_OUTSIDE_ROOT",
            "PATH_SYMLINK_ESCAPE",
            "PATH_UNSAFE",
        }:
            return "", b"", str(exc)
        raise


def verify_expected_digest(root: Path, relative: str, expected: str | None) -> bool | None:
    if expected is None:
        return None
    try:
        path = resolve_source_file(root, relative)
        data = path.read_bytes()
    except (TaskContextError, OSError):
        return False
    from project_atlas.task_context.models import sha256_bytes

    return sha256_bytes(data) == expected
