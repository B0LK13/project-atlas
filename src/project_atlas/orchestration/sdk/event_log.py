"""Append-only supervisor lifecycle events. Safe fields only; no secrets."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE

EVENT_LOG_NAME: Final[str] = "events.jsonl"
EVENT_WITNESS_NAME: Final[str] = "event-witness.jsonl"

SupervisorEventName = Literal[
    "TARGET_HEAD_OBSERVED",
    "OLD_CI_CANCELLED",
    "OLD_CI_SUPERSEDED",
    "NEW_HEAD_ADOPTED",
    "NEW_CI_ADOPTED",
    "CI_TERMINAL",
    "CI_JOB_SIGNAL",
    "CLOUD_AUDIT_DISPATCHED",
    "IV_DISPATCHED",
    "ADV_DISPATCHED",
    "REMEDIATION_DISPATCHED",
    "SDK_AGENT_CREATED",
    "SDK_RUN_CREATED",
    "SDK_RUN_FINISHED",
    "SDK_AGENT_RESUMED",
    "CANDIDATE_CERTIFIED",
]


class SupervisorEvent(BaseModel):
    """One durable lifecycle event. Prompt/secret payloads are forbidden."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str
    event: SupervisorEventName
    dag_generation: int = Field(ge=0, le=1_000_000)
    head: str | None = None
    tree: str | None = None
    node: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    detail: str | None = None


def event_log_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / EVENT_LOG_NAME


def event_witness_path(root: Path) -> Path:
    """Append-only witness that is not part of the live/route/high-water trio."""
    return root / STATE_DIR_RELATIVE / EVENT_WITNESS_NAME


def _append_event_witness(root: Path, *, line: str, dag_generation: int) -> None:
    path = event_witness_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    if path.is_file():
        body = path.read_text(encoding="utf-8").splitlines()
        if body:
            previous = body[-1]
    digest = hashlib.sha256(f"{previous}\n{line}".encode()).hexdigest()
    record = {
        "event_digest": hashlib.sha256(line.encode("utf-8")).hexdigest(),
        "chain": digest,
        "dag_generation": dag_generation,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_event_witness(root: Path) -> list[dict[str, object]]:
    path = event_witness_path(root)
    if not path.is_file():
        return []
    out: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("corrupt event witness") from exc
        if not isinstance(item, dict):
            raise ValueError("corrupt event witness")
        out.append(item)
    return out


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_event(
    root: Path,
    event: SupervisorEventName,
    *,
    dag_generation: int,
    head: str | None = None,
    tree: str | None = None,
    node: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    detail: str | None = None,
) -> SupervisorEvent:
    record = SupervisorEvent(
        timestamp=_utc_now(),
        event=event,
        dag_generation=dag_generation,
        head=head,
        tree=tree,
        node=node,
        agent_id=agent_id,
        run_id=run_id,
        detail=detail,
    )
    path = event_log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = record.model_dump_json()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    _append_event_witness(root, line=line, dag_generation=dag_generation)
    return record


def read_events(root: Path) -> list[SupervisorEvent]:
    path = event_log_path(root)
    if not path.is_file():
        return []
    events: list[SupervisorEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        events.append(SupervisorEvent.model_validate_json(raw))
    return events
