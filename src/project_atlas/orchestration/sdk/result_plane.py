"""Shared governor result plane — mandatory binding, consume-once, no owner relay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRole,
    RunRecord,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.registries import RunRegistry
from project_atlas.orchestration.sdk.security_gates import (
    BoundWorkerResult,
    WorkerBackend,
    validate_result_binding,
)

RESULT_PLANE_NAME = "result-plane.jsonl"
INGESTED_NAME = "result-plane-ingested.json"
TRANSPORT_PROOF_NAME = "result-plane-transport-proof.json"


class ResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source: Literal["IV", "ADV", "CLI_WORKER", "CLOUD_AUDITOR", "SDK_WORKER"]
    binding: BoundWorkerResult
    payload: dict[str, Any] = Field(default_factory=dict)
    owner_relay_required: Literal[False] = False


class TransportProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_written: bool = False
    supervisor_discovered: bool = False
    binding_validated: bool = False
    result_consumed: bool = False
    dag_transition_occurred: bool = False
    owner_relay: Literal[False] = False
    consumed_result_ids: tuple[str, ...] = ()


def result_plane_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / RESULT_PLANE_NAME


def ingested_index_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / INGESTED_NAME


def transport_proof_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / TRANSPORT_PROOF_NAME


def result_id(*, run_id: str, result_digest: str) -> str:
    return f"{run_id}+{result_digest}"


def append_result(root: Path, envelope: ResultEnvelope) -> Path:
    if envelope.owner_relay_required:
        raise SdkRuntimeError("owner relay forbidden", code="OWNER_RELAY_FORBIDDEN")
    path = result_plane_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(envelope.model_dump_json() + "\n")
    proof = load_transport_proof(root)
    proof = proof.model_copy(update={"result_written": True})
    persist_transport_proof(root, proof)
    return path


def load_transport_proof(root: Path) -> TransportProof:
    path = transport_proof_path(root)
    if path.is_file():
        try:
            return TransportProof.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return TransportProof()


def persist_transport_proof(root: Path, proof: TransportProof) -> Path:
    path = transport_proof_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _load_consumed(root: Path) -> set[str]:
    path = ingested_index_path(root)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = data.get("result_ids") if isinstance(data, dict) else None
    if isinstance(ids, list):
        return {str(x) for x in ids}
    # Legacy digest-only index → treat as consumed digests (migration).
    digests = data.get("digests") if isinstance(data, dict) else None
    if isinstance(digests, list):
        return {f"*+{d}" for d in digests}
    return set()


def _save_consumed(root: Path, result_ids: set[str]) -> None:
    path = ingested_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"result_ids": sorted(result_ids)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def expected_binding_from_run(
    run: RunRecord,
    *,
    worker_backend: WorkerBackend,
    result_digest: str,
) -> dict[str, Any]:
    if not run.lease_id:
        raise SdkRuntimeError("run missing lease for binding", code="LEASE_REQUIRED")
    if not run.node_id:
        raise SdkRuntimeError("run missing node for binding", code="BINDING_MISMATCH")
    return {
        "worker_backend": worker_backend.value,
        "session_or_agent_id": run.agent_id,
        "run_id": run.run_id,
        "package_id": run.package_id,
        "dag_node": run.node_id,
        "dag_generation": run.dag_generation,
        "role": run.role.value,
        "lease_id": run.lease_id,
        "attempt": run.attempt,
        "result_digest": result_digest,
        "candidate_head": run.candidate_head,
        "candidate_tree": run.candidate_tree,
    }


def ingest_pending_against_registry(
    root: Path,
    *,
    runs: RunRegistry,
    worker_backend: WorkerBackend = WorkerBackend.CURSOR_AGENT_CLI,
    mark_dag_transition: bool = True,
) -> list[BoundWorkerResult]:
    """Authoritative ingest: derive expected binding from RunRegistry by RUN_ID."""
    path = result_plane_path(root)
    if not path.is_file():
        return []
    proof = load_transport_proof(root).model_copy(update={"supervisor_discovered": True})
    consumed = _load_consumed(root)
    accepted: list[BoundWorkerResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            envelope = ResultEnvelope.model_validate_json(line)
        except ValueError:
            continue
        binding = envelope.binding
        rid = result_id(run_id=binding.run_id, result_digest=binding.result_digest)
        if rid in consumed or f"*+{binding.result_digest}" in consumed:
            continue
        stored = runs.get(binding.run_id)
        if stored is None:
            raise SdkRuntimeError("result run not in registry", code="FOREIGN_RESULT")
        expected = expected_binding_from_run(
            stored,
            worker_backend=worker_backend,
            result_digest=binding.result_digest,
        )
        if stored.package_id != PACKAGE_ID:
            raise SdkRuntimeError("foreign package in run registry", code="FOREIGN_RESULT")
        validate_result_binding(
            binding,
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
            seen_digests={c.split("+", 1)[-1] for c in consumed if "+" in c},
        )
        proof = proof.model_copy(update={"binding_validated": True})
        consumed.add(rid)
        accepted.append(binding)
        proof = proof.model_copy(
            update={
                "result_consumed": True,
                "consumed_result_ids": tuple(
                    sorted(set(proof.consumed_result_ids) | {rid})
                ),
                "dag_transition_occurred": bool(mark_dag_transition and accepted),
            }
        )
    _save_consumed(root, consumed)
    persist_transport_proof(root, proof)
    return accepted


def ingest_pending(
    root: Path,
    *,
    expected: dict[str, Any] | None = None,
) -> list[BoundWorkerResult]:
    """Actionable ingest requires expected binding derived by the caller from RunRegistry.

    Calling with expected=None is forbidden for current-route actionable results.
    """
    if expected is None:
        raise SdkRuntimeError(
            "expected binding mandatory for actionable ingest",
            code="EXPECTED_BINDING_REQUIRED",
        )
    path = result_plane_path(root)
    if not path.is_file():
        return []
    consumed = _load_consumed(root)
    accepted: list[BoundWorkerResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            envelope = ResultEnvelope.model_validate_json(line)
        except ValueError:
            continue
        binding = envelope.binding
        rid = result_id(run_id=binding.run_id, result_digest=binding.result_digest)
        if rid in consumed:
            continue
        validate_result_binding(
            binding,
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
            seen_digests={c.split("+", 1)[-1] for c in consumed if "+" in c},
        )
        consumed.add(rid)
        accepted.append(binding)
    _save_consumed(root, consumed)
    proof = load_transport_proof(root)
    if accepted:
        proof = proof.model_copy(
            update={
                "supervisor_discovered": True,
                "binding_validated": True,
                "result_consumed": True,
                "dag_transition_occurred": True,
                "consumed_result_ids": tuple(
                    sorted(
                        set(proof.consumed_result_ids)
                        | {
                            result_id(run_id=a.run_id, result_digest=a.result_digest)
                            for a in accepted
                        }
                    )
                ),
            }
        )
        persist_transport_proof(root, proof)
    return accepted


def transport_state(root: Path) -> Literal["CLOSED", "OPEN", "NOT_APPLICABLE"]:
    """CLOSED only after end-to-end write→discover→validate→consume→transition."""
    proof = load_transport_proof(root)
    if (
        proof.result_written
        and proof.supervisor_discovered
        and proof.binding_validated
        and proof.result_consumed
        and proof.dag_transition_occurred
        and proof.owner_relay is False
    ):
        return "CLOSED"
    return "OPEN"
