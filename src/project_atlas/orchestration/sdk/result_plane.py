"""Shared governor result plane — ingest IV/ADV/CLI/cloud results without owner relay.

Closes ORCH_CROSS_AGENT_RESULT_TRANSPORT_001 when writers persist here and the
supervisor consumes without human copy/paste.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, AgentRole, SdkRuntimeError
from project_atlas.orchestration.sdk.security_gates import (
    BoundWorkerResult,
    WorkerBackend,
    validate_result_binding,
)

RESULT_PLANE_NAME = "result-plane.jsonl"
INGESTED_NAME = "result-plane-ingested.json"


class ResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source: Literal["IV", "ADV", "CLI_WORKER", "CLOUD_AUDITOR", "SDK_WORKER"]
    binding: BoundWorkerResult
    payload: dict[str, Any] = Field(default_factory=dict)
    owner_relay_required: Literal[False] = False


def result_plane_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / RESULT_PLANE_NAME


def ingested_index_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / INGESTED_NAME


def append_result(root: Path, envelope: ResultEnvelope) -> Path:
    if envelope.owner_relay_required:
        raise SdkRuntimeError("owner relay forbidden", code="OWNER_RELAY_FORBIDDEN")
    path = result_plane_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(envelope.model_dump_json() + "\n")
    return path


def _load_ingested(root: Path) -> set[str]:
    path = ingested_index_path(root)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    digests = data.get("digests") if isinstance(data, dict) else None
    if not isinstance(digests, list):
        return set()
    return {str(x) for x in digests}


def _save_ingested(root: Path, digests: set[str]) -> None:
    path = ingested_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"digests": sorted(digests)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ingest_pending(
    root: Path,
    *,
    expected: dict[str, Any] | None = None,
) -> list[BoundWorkerResult]:
    """Consume new envelopes. Optional expected binding rejects foreign/stale."""
    path = result_plane_path(root)
    if not path.is_file():
        return []
    seen = _load_ingested(root)
    accepted: list[BoundWorkerResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            envelope = ResultEnvelope.model_validate_json(line)
        except ValueError:
            continue
        digest = envelope.binding.result_digest
        if digest in seen:
            continue
        if expected:
            validate_result_binding(
                envelope.binding,
                expected_backend=WorkerBackend(expected["worker_backend"]),
                expected_session=str(expected["session_or_agent_id"]),
                expected_run=str(expected["run_id"]),
                expected_package=str(expected["package_id"]),
                expected_node=str(expected["dag_node"]),
                expected_generation=int(expected["dag_generation"]),
                expected_role=AgentRole(expected["role"]),
                expected_lease=str(expected["lease_id"]),
                expected_attempt=int(expected["attempt"]),
                expected_digest=str(expected["result_digest"]),
                expected_head=expected.get("candidate_head"),
                expected_tree=expected.get("candidate_tree"),
                seen_digests=seen,
            )
        seen.add(digest)
        accepted.append(envelope.binding)
    _save_ingested(root, seen)
    return accepted


def transport_state(root: Path) -> Literal["CLOSED", "OPEN", "NOT_APPLICABLE"]:
    path = result_plane_path(root)
    if path.is_file():
        return "CLOSED"
    return "OPEN"
