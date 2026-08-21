"""Exact Cloud run recovery after fresh-client reconnect (D-119).

Uses only documented Cursor SDK surfaces:
  client.agents.resume(agent_id)
  client.agents.get_run(run_id)
  client.agents.list_runs(agent_id)

Never selects latest/first/newest terminal run. Exact run_id match only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from project_atlas.orchestration.sdk.models import (
    AgentRecord,
    AgentRuntime,
    RunRecord,
    SdkRuntimeError,
)


class CloudRunRecoveryClass(StrEnum):
    DIRECT_GET_RUN_OK = "DIRECT_GET_RUN_OK"
    LIST_RUNS_EXACT_MATCH = "LIST_RUNS_EXACT_MATCH"
    REATTACHED_GET_RUN_OK = "REATTACHED_GET_RUN_OK"
    CLOUD_RUN_RECOVERY_UNDETERMINED = "CLOUD_RUN_RECOVERY_UNDETERMINED"
    FOREIGN_RECOVERED_RUN = "FOREIGN_RECOVERED_RUN"
    AMBIGUOUS_RECOVERED_RUN = "AMBIGUOUS_RECOVERED_RUN"


@dataclass(frozen=True)
class RecoveredCloudRun:
    """Exact recovered Cloud run snapshot. Evidence only — not authority."""

    agent_id: str
    run_id: str
    snapshot: Any
    classification: CloudRunRecoveryClass


def is_get_run_reconnect_miss(exc: BaseException) -> bool:
    """True when a fresh client miss looks like reconnect/not-found, not auth death."""
    text = f"{type(exc).__name__}:{exc}".casefold()
    needles = (
        "not found",
        "invalid_argument",
        "badrequesterror",
        "unknown run",
        "run not found",
        "does not exist",
    )
    return any(n in text for n in needles)


def _run_id_of(snapshot: Any) -> str | None:
    for name in ("id", "run_id", "runId"):
        if isinstance(snapshot, dict) and name in snapshot:
            value = snapshot[name]
            return str(value) if value is not None else None
        value = getattr(snapshot, name, None)
        if value is not None:
            return str(value)
    return None


def _agent_id_of(snapshot: Any) -> str | None:
    for name in ("agent_id", "agentId"):
        if isinstance(snapshot, dict) and name in snapshot:
            value = snapshot[name]
            return str(value) if value is not None else None
        value = getattr(snapshot, name, None)
        if value is not None:
            return str(value)
    return None


def validate_persisted_cloud_binding(
    *,
    agent: AgentRecord,
    run: RunRecord,
    agent_id: str,
    run_id: str,
) -> None:
    if agent.runtime != AgentRuntime.CLOUD:
        raise SdkRuntimeError(
            "recover_exact_cloud_run requires CLOUD agent runtime",
            code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
        )
    if not agent_id.startswith("bc-"):
        raise SdkRuntimeError(
            "recover_exact_cloud_run requires bc-* agent_id",
            code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
        )
    if run.agent_id != agent_id or agent.agent_id != agent_id:
        raise SdkRuntimeError(
            "persisted agent/run binding mismatch",
            code=CloudRunRecoveryClass.FOREIGN_RECOVERED_RUN.value,
        )
    if run.run_id != run_id:
        raise SdkRuntimeError(
            "persisted run_id mismatch",
            code=CloudRunRecoveryClass.FOREIGN_RECOVERED_RUN.value,
        )


def _validate_snapshot_binding(
    snapshot: Any, *, agent_id: str, run_id: str
) -> CloudRunRecoveryClass | None:
    """Return failure class if snapshot binding is wrong; None if OK."""
    snap_run = _run_id_of(snapshot)
    if snap_run is not None and snap_run != run_id:
        return CloudRunRecoveryClass.FOREIGN_RECOVERED_RUN
    snap_agent = _agent_id_of(snapshot)
    if snap_agent is not None and snap_agent != agent_id:
        return CloudRunRecoveryClass.FOREIGN_RECOVERED_RUN
    return None


async def _page_list_runs_exact(
    client: Any, *, agent_id: str, run_id: str, api_key: str | None
) -> list[Any]:
    """Page list_runs; collect ONLY candidates whose id == run_id."""
    matches: list[Any] = []
    opts: dict[str, Any] = {}
    if api_key:
        opts["api_key"] = api_key
    cursor: str | None = None
    pages = 0
    while pages < 50:
        pages += 1
        if cursor:
            listing = await client.agents.list_runs(
                agent_id, opts or None, cursor=cursor
            )
        else:
            listing = await client.agents.list_runs(agent_id, opts or None)
        items = getattr(listing, "items", None) or []
        for item in items:
            if _run_id_of(item) == run_id:
                matches.append(item)
        next_cursor = getattr(listing, "next_cursor", None) or getattr(
            listing, "nextCursor", None
        )
        if not next_cursor:
            break
        cursor = str(next_cursor)
    return matches


async def recover_exact_cloud_run(
    *,
    client: Any,
    agent: AgentRecord,
    run: RunRecord,
    agent_id: str,
    run_id: str,
    api_key: str | None = None,
    resume: Any | None = None,
) -> RecoveredCloudRun:
    """Reattach + exact get_run / list_runs recovery. Never mark_terminal."""
    validate_persisted_cloud_binding(
        agent=agent, run=run, agent_id=agent_id, run_id=run_id
    )

    # 3. Reattach
    if resume is not None:
        await resume(agent_id)
    else:
        from cursor_sdk import AgentOptions

        opts: dict[str, Any] = {}
        if api_key:
            opts["api_key"] = api_key
        await client.agents.resume(
            agent_id, AgentOptions(**opts) if opts else AgentOptions()
        )

    # 4. Primary get_run
    try:
        snapshot = await client.agents.get_run(run_id)
        bad = _validate_snapshot_binding(
            snapshot, agent_id=agent_id, run_id=run_id
        )
        if bad is not None:
            raise SdkRuntimeError(
                "recovered run binding mismatch",
                code=bad.value,
            )
        return RecoveredCloudRun(
            agent_id=agent_id,
            run_id=run_id,
            snapshot=snapshot,
            classification=CloudRunRecoveryClass.DIRECT_GET_RUN_OK,
        )
    except SdkRuntimeError:
        raise
    except Exception as exc:
        if not is_get_run_reconnect_miss(exc):
            raise SdkRuntimeError(
                f"cloud get_run failed: {exc}",
                code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
            ) from exc

    # 6-8. list_runs exact match only
    try:
        matches = await _page_list_runs_exact(
            client, agent_id=agent_id, run_id=run_id, api_key=api_key
        )
    except Exception as exc:
        raise SdkRuntimeError(
            f"cloud list_runs failed: {exc}",
            code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
        ) from exc

    if len(matches) > 1:
        raise SdkRuntimeError(
            "ambiguous exact run_id matches in list_runs",
            code=CloudRunRecoveryClass.AMBIGUOUS_RECOVERED_RUN.value,
        )
    if len(matches) == 0:
        raise SdkRuntimeError(
            "get_run miss and list_runs has no exact run_id",
            code=CloudRunRecoveryClass.CLOUD_RUN_RECOVERY_UNDETERMINED.value,
        )

    listed = matches[0]
    bad = _validate_snapshot_binding(listed, agent_id=agent_id, run_id=run_id)
    if bad is not None:
        raise SdkRuntimeError(
            "list_runs exact match failed binding check",
            code=bad.value,
        )

    # Prefer full get_run after reattach when list only proves existence
    try:
        snapshot = await client.agents.get_run(run_id)
        bad = _validate_snapshot_binding(
            snapshot, agent_id=agent_id, run_id=run_id
        )
        if bad is not None:
            raise SdkRuntimeError(
                "reattached get_run binding mismatch",
                code=bad.value,
            )
        return RecoveredCloudRun(
            agent_id=agent_id,
            run_id=run_id,
            snapshot=snapshot,
            classification=CloudRunRecoveryClass.REATTACHED_GET_RUN_OK,
        )
    except SdkRuntimeError:
        raise
    except Exception:
        # Summary-only list match: use listed snapshot if it carries git metadata
        return RecoveredCloudRun(
            agent_id=agent_id,
            run_id=run_id,
            snapshot=listed,
            classification=CloudRunRecoveryClass.LIST_RUNS_EXACT_MATCH,
        )
