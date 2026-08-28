"""AS-ORCH-CONTINUATION-BROKER-001 / D-082 — Cursor SDK durable agent runtime.

PRIMARY_CONTINUATION_BACKEND = CURSOR_SDK_DURABLE_AGENT_RUNTIME
STOP_HOOK_BACKEND = FALLBACK

Cursor agents are workers. The Atlas primary governor owns the DAG.
RUN_TERMINAL != DAG_END. Result != authority. No second governor.
"""

from __future__ import annotations

from project_atlas.orchestration.sdk.auth import (
    AuthDiscovery,
    discover_auth,
    record_auth_prerequisite,
)
from project_atlas.orchestration.sdk.models import (
    DIRECTIVE_ID,
    PACKAGE_ID,
    PRIMARY_BACKEND,
    STOP_HOOK_BACKEND,
    AgentRecord,
    AgentRole,
    AgentRuntime,
    RunRecord,
    RunStatus,
)
from project_atlas.orchestration.sdk.supervisor import DurableAtlasSupervisor

__all__ = [
    "DIRECTIVE_ID",
    "PACKAGE_ID",
    "PRIMARY_BACKEND",
    "STOP_HOOK_BACKEND",
    "AgentRecord",
    "AgentRole",
    "AgentRuntime",
    "AuthDiscovery",
    "DurableAtlasSupervisor",
    "RunRecord",
    "RunStatus",
    "discover_auth",
    "record_auth_prerequisite",
]
