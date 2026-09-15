"""AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001 — standing mission (not authority).

Mission survives restart. Never stores secrets. Never grants merge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, SdkRuntimeError

PACKAGE_ID: Final[Literal["AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001"]] = (
    "AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001"
)
MISSION_NAME: Final[str] = "resident-mission.json"
STACKED_DEPENDENCY: Final[str] = "PR433"
MERGE_ORDER: Final[str] = "PR433 -> SELF_WAKE_DRIVER"


class ResidentMission(BaseModel):
    """Standing autonomous mission. Observability + recovery only."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001"] = PACKAGE_ID
    PROJECT: Literal["PROJECT_ATLAS"] = "PROJECT_ATLAS"
    MODE: Literal["PERSISTENT_EVENT_DRIVEN_AUTONOMOUS_DEVELOPER"] = (
        "PERSISTENT_EVENT_DRIVEN_AUTONOMOUS_DEVELOPER"
    )
    DEFAULT_CERT_PROTOCOL: Literal["AS-ORCH-SPECULATIVE-CERTIFICATION-001"] = (
        "AS-ORCH-SPECULATIVE-CERTIFICATION-001"
    )
    AUTO_DISPATCH: Literal["YES"] = "YES"
    FUTURE_AUTO_MERGE: Literal["NO"] = "NO"
    OWNER_HELD_DOES_NOT_STOP_GLOBAL_DAG: Literal["YES"] = "YES"
    RESOURCE_YIELD_IS_NOT_OWNER_REQUIRED: Literal["YES"] = "YES"
    EXTERNAL_WAIT_IS_NOT_GLOBAL_WAIT: Literal["YES"] = "YES"
    EXTERNAL_TRIGGER_REQUIRED_FOR_NEXT_SCHEDULER_TICK: Literal["NO"] = "NO"
    FOLLOWUP_MESSAGE_REQUIRED_FOR_NORMAL_PROGRESS: Literal["NO"] = "NO"
    MANUAL_OWNER_MESSAGE_REQUIRED_TO_ADVANCE_NORMAL_DAG: Literal["NO"] = "NO"
    OUTER_SESSION_EXIT_STOPS_DAG: Literal["NO"] = "NO"
    GOVERNOR_CRASH_REQUIRES_OWNER_CONTINUE_MESSAGE: Literal["NO"] = "NO"
    MERGE_AUTHORIZATION: Literal["NOT_GRANTED"] = "NOT_GRANTED"
    STACKED_DEPENDENCY: Literal["PR433"] = "PR433"
    MERGE_ORDER: Literal["PR433 -> SELF_WAKE_DRIVER"] = "PR433 -> SELF_WAKE_DRIVER"
    service_enabled: bool = True
    heartbeat_cap_sec: float = Field(default=5.0, ge=0.1, le=60.0)
    stall_interval_sec: float = Field(default=30.0, ge=1.0, le=600.0)
    merge_authorized: Literal[False] = False


def mission_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / MISSION_NAME


def default_mission() -> ResidentMission:
    return ResidentMission()


def persist_mission(root: Path, mission: ResidentMission | None = None) -> ResidentMission:
    payload = (mission or default_mission()).model_copy(
        update={"merge_authorized": False}
    )
    path = mission_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload


def load_mission(root: Path) -> ResidentMission:
    path = mission_path(root)
    if not path.is_file():
        return persist_mission(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkRuntimeError(
            "resident mission unreadable", code="MISSION_MALFORMED"
        ) from exc
    if not isinstance(data, dict):
        raise SdkRuntimeError("resident mission not object", code="MISSION_MALFORMED")
    data["merge_authorized"] = False
    data["FUTURE_AUTO_MERGE"] = "NO"
    data["MERGE_AUTHORIZATION"] = "NOT_GRANTED"
    return ResidentMission.model_validate(data)
