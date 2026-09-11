"""Assemble, freshness-check, compare, and render task-context packets."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_atlas.task_context.adapters import (
    ContractSnapshot,
    contract_digest,
    load_contract,
    load_evidence_bundle,
)
from project_atlas.task_context.budget import apply_budget
from project_atlas.task_context.compare import compare_packets as _compare_packets
from project_atlas.task_context.freshness import diagnose_freshness, git_head_identity
from project_atlas.task_context.models import (
    PACKAGE_ID,
    ContractBinding,
    TaskContextError,
    TaskContextPacket,
    content_digest,
    honesty_defaults,
)
from project_atlas.task_context.select import (
    build_requirement_fragments,
    prior_actions_from_evidence,
    select_retrieved_fragments,
)
from project_atlas.task_context.views import render_human_summary, render_view

DEFAULT_BUDGET_CHARS = 48_000


def _observation_time() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _packet_id(contract_id: str, digest: str) -> str:
    slug = contract_id.lower().replace("_", "-")[:48]
    return f"tcp-{slug}-{digest[:12]}"


def assemble_packet(
    *,
    contract: ContractSnapshot | Path,
    workspace_root: Path,
    evidence_path: Path | None = None,
    budget_chars: int = DEFAULT_BUDGET_CHARS,
    search_hook: Callable[[str], list[tuple[str, str]]] | None = None,
    observation_time: str | None = None,
    candidate_identity: str | None = None,
) -> TaskContextPacket:
    """Build a deterministic content packet for one contract.

    Does not execute commands found in documents or transcripts.
    """
    if isinstance(contract, Path):  # noqa: SIM108 — keep explicit branches
        snapshot = load_contract(contract, prefer_live=True)
    else:
        snapshot = contract

    # Hard guard: retrieved text never mutates the contract mutation set.
    mutation_paths = tuple(snapshot.mutation_paths)
    cdigest = contract_digest(snapshot)

    req_frags = build_requirement_fragments(snapshot)
    retrieved, uncertainties, limits = select_retrieved_fragments(
        snapshot, workspace_root=workspace_root, search_hook=search_hook
    )

    # Structural enforcement: no retrieved fragment may alter mutation_paths.
    for frag in retrieved:
        if frag.included and frag.body:
            # Detect self-promotion attempts; keep as uncertainty, never apply.
            lowered = frag.body.lower()
            if "mutation scope" in lowered and (
                "all files" in lowered or "any file" in lowered or "widen" in lowered
            ):
                # Already flagged via injection markers in select; ensure scope unchanged.
                pass
    assert list(mutation_paths) == list(snapshot.mutation_paths)

    evidence_records = load_evidence_bundle(evidence_path) if evidence_path else ()
    prior = prior_actions_from_evidence(evidence_records)

    all_frags = list(req_frags) + list(retrieved)
    budgeted, budget_report = apply_budget(all_frags, budget_chars=budget_chars)

    req_ids = tuple(
        str(r.get("requirement_id"))
        for r in snapshot.requirements
        if isinstance(r, dict) and r.get("requirement_id")
    )
    acc_ids = tuple(
        str(a.get("check_id") or a.get("id"))
        for a in snapshot.acceptance
        if isinstance(a, dict) and (a.get("check_id") or a.get("id"))
    )

    binding = ContractBinding(
        contract_id=snapshot.contract_id,
        contract_digest=cdigest,
        contract_version=snapshot.contract_version,
        repository=snapshot.repository,
        candidate_identity=candidate_identity or snapshot.candidate_identity or git_head_identity(
            workspace_root
        ),
        objective=snapshot.objective,
        observable_outcome=snapshot.observable_outcome,
        mutation_paths=mutation_paths,
        scope=tuple(snapshot.scope),
        exclusions=tuple(snapshot.exclusions),
        policy_refs=tuple(snapshot.policy_refs),
        acceptance_ids=acc_ids,
        requirement_ids=req_ids,
    )

    draft = TaskContextPacket(
        packet_id="tcp-pending",
        content_digest="0" * 64,
        contract=binding,
        fragments=tuple(budgeted),
        prior_actions=tuple(prior),
        uncertainties=tuple(uncertainties),
        selection_limits=tuple(limits),
        honesty=honesty_defaults(),
        observation_time=observation_time or _observation_time(),
        budget_report=budget_report,
        report_metadata={
            "workspace_root": str(workspace_root),
            "contract_source_kind": snapshot.source_kind,
            "evidence_source_kind": (
                evidence_records[0].source_kind if evidence_records else "none"
            ),
        },
        generated={"by": PACKAGE_ID},
    )
    digest = content_digest(draft)
    return draft.model_copy(
        update={
            "packet_id": _packet_id(snapshot.contract_id, digest),
            "content_digest": digest,
        }
    )


def check_freshness(
    packet: TaskContextPacket | Path | dict[str, Any],
    *,
    workspace_root: Path,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    if isinstance(packet, Path):
        raw = json.loads(packet.read_text(encoding="utf-8"))
        packet = TaskContextPacket.model_validate(raw)
    elif isinstance(packet, dict):
        packet = TaskContextPacket.model_validate(packet)
    return diagnose_freshness(
        packet, workspace_root=workspace_root, contract_path=contract_path
    )


def compare_packets(
    left: TaskContextPacket | Path | dict[str, Any],
    right: TaskContextPacket | Path | dict[str, Any],
) -> dict[str, Any]:
    def _load(value: TaskContextPacket | Path | dict[str, Any]) -> TaskContextPacket:
        if isinstance(value, TaskContextPacket):
            return value
        if isinstance(value, Path):
            return TaskContextPacket.model_validate(
                json.loads(value.read_text(encoding="utf-8"))
            )
        return TaskContextPacket.model_validate(value)

    return _compare_packets(_load(left), _load(right))


def write_packet(packet: TaskContextPacket, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    payload = packet.model_dump(mode="json")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(output)


def load_packet(path: Path) -> TaskContextPacket:
    try:
        return TaskContextPacket.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise TaskContextError(f"packet unreadable: {exc}", code="PACKET_UNREADABLE") from exc


# Re-export render helpers for package API.
__all__ = [
    "TaskContextError",
    "assemble_packet",
    "check_freshness",
    "compare_packets",
    "load_packet",
    "render_human_summary",
    "render_view",
    "write_packet",
]
