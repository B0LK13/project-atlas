"""AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001 — resident status (observability only)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE

STATUS_NAME: Final[str] = "resident-status.json"
PACKAGE_ID: Final[str] = "AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001"


class ResidentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001"] = PACKAGE_ID  # type: ignore[assignment]
    GOVERNOR_PID: int = 0
    SERVICE_INSTANCE_ID: str = ""
    STARTED_AT: float = 0.0
    LAST_SCHEDULER_TICK: float = 0.0
    LAST_PROGRESS_AT: float = 0.0
    NEXT_WAKE_AT: float | None = None
    READY_NODE_COUNT: int = 0
    ACTIVE_WORKER_COUNT: int = 0
    PENDING_EXTERNAL_EVENT_COUNT: int = 0
    OWNER_HELD_COUNT: int = 0
    LAST_EVENT_CONSUMED: str | None = None
    LAST_NODE_DISPATCHED: str | None = None
    DETACHED_SCHEDULER_TICK_COUNT: int = 0
    MANUAL_CONTINUE_COUNT: int = 0
    LOST_EVENT_COUNT: int = 0
    DUPLICATE_DISPATCH_COUNT: int = 0
    GLOBAL_OWNER_REQUIRED: Literal["YES", "NO"] = "NO"
    RESIDENT_GOVERNOR: Literal["YES"] = "YES"
    SESSION_BOUND_GOVERNOR: Literal["NO"] = "NO"
    SELF_WAKE_DRIVER: Literal["ACTIVE", "STOPPED"] = "ACTIVE"
    EXTERNAL_TRIGGER_REQUIRED_FOR_NEXT_SCHEDULER_TICK: Literal["NO"] = "NO"
    CURSOR_API_KEY_PRESENT: Literal["YES", "NO"] = "NO"
    AUTHENTICATION_WORKS: Literal["YES", "NO", "UNKNOWN"] = "UNKNOWN"
    SECRET_LEAK_COUNT: int = 0
    merge_authorized: Literal[False] = False


def status_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / STATUS_NAME


def load_status(root: Path) -> ResidentStatus:
    path = status_path(root)
    if not path.is_file():
        return ResidentStatus(STARTED_AT=time.time())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ResidentStatus(STARTED_AT=time.time())
    if not isinstance(data, dict):
        return ResidentStatus(STARTED_AT=time.time())
    data["merge_authorized"] = False
    return ResidentStatus.model_validate(data)


def persist_status(root: Path, status: ResidentStatus) -> ResidentStatus:
    payload = status.model_copy(update={"merge_authorized": False})
    path = status_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
