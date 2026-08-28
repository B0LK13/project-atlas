"""Adapt SDK terminal results into governor-ingestible evidence. Never authority."""

from __future__ import annotations

from typing import Any

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.sdk.models import (
    IngestedRunResult,
    RunStatus,
    SdkRuntimeError,
)


def normalize_run_status(raw: str | None) -> RunStatus:
    if raw is None:
        return RunStatus.UNKNOWN
    mapping = {
        "finished": RunStatus.FINISHED,
        "error": RunStatus.ERROR,
        "cancelled": RunStatus.CANCELLED,
        "canceled": RunStatus.CANCELLED,
        "running": RunStatus.RUNNING,
        "creating": RunStatus.CREATING,
    }
    return mapping.get(str(raw).lower(), RunStatus.UNKNOWN)


def adapt_run_result(
    *,
    run_id: str,
    agent_id: str,
    status: str | RunStatus,
    result_text: str | None = None,
    git_metadata: dict[str, Any] | None = None,
    token_usage_total: int | None = None,
    cost_charged_cents: float | None = None,
    claimed_merge_authorized: bool = False,
    claimed_execution_authorized: bool = False,
    claimed_authority_granted: bool = False,
) -> IngestedRunResult:
    """Map SDK output to ingest record. Authority claims are rejected."""
    if claimed_merge_authorized or claimed_execution_authorized or claimed_authority_granted:
        raise SdkRuntimeError(
            "result attempted to grant authority",
            code="AUTHORITY_INJECTION",
        )
    if not run_id or not agent_id:
        raise SdkRuntimeError("forged empty run/agent id", code="FORGED_ID")
    status_enum = status if isinstance(status, RunStatus) else normalize_run_status(status)
    text = result_text or ""
    payload = {
        "run_id": run_id,
        "agent_id": agent_id,
        "status": status_enum.value,
        "result_text": text,
        "git": git_metadata or {},
    }
    digest = hash_payload(payload)
    text_digest = hash_payload({"text": text}) if text else None
    head = None
    tree = None
    if git_metadata:
        head = git_metadata.get("head") or git_metadata.get("commit")
        tree = git_metadata.get("tree")
        if head is not None:
            head = str(head)
        if tree is not None:
            tree = str(tree)
    return IngestedRunResult(
        run_id=run_id,
        agent_id=agent_id,
        status=status_enum,
        result_digest=digest,
        result_text_digest=text_digest,
        candidate_head=head if isinstance(head, str) and len(head) == 40 else None,
        candidate_tree=tree if isinstance(tree, str) and len(tree) == 40 else None,
        token_usage_total=token_usage_total,
        cost_charged_cents=cost_charged_cents,
    )
