"""Authenticated local Cursor Agent / ACP fallback.

Does not reuse 001D Ask-mode flags. Mutation requires Agent mode.
API keys are never written to host/broker state.
"""

from __future__ import annotations

from collections.abc import Iterable
from shutil import which

from project_atlas.orchestration.autonomy.mutating_transport import (
    MutatingLaunchReceipt,
    MutatingLeaseBinding,
    MutatingTransportError,
    WorkerBackendType,
    local_cursor_cli_present,
    require_active_lease,
)


class LocalAgentBackend:
    """Discover-only until an authenticated Agent/ACP session is present."""

    def start(
        self,
        binding: MutatingLeaseBinding,
        prompt: str,
        leases: Iterable[object] | None = None,
    ) -> MutatingLaunchReceipt:
        del prompt
        require_active_lease(leases, binding)
        if binding.merge_authorized or binding.direct_main:
            raise MutatingTransportError(
                "local agent cannot carry merge authority",
                code="AUTHORITY_DENIED",
            )
        if not local_cursor_cli_present():
            raise MutatingTransportError("local cursor agent is absent", code="LOCAL_AGENT_ABSENT")
        raise MutatingTransportError(
            "local cursor agent is present but not authenticated in this host",
            code="LOCAL_AGENT_UNAUTHENTICATED",
        )

    def recover(self, agent_id: str, run_id: str) -> MutatingLaunchReceipt:
        del agent_id, run_id
        raise MutatingTransportError("no local agent run to recover", code="UNKNOWN_WORKER")

    def follow_up(
        self,
        agent_id: str,
        prompt: str,
        leases: Iterable[object] | None = None,
    ) -> MutatingLaunchReceipt:
        del agent_id, prompt, leases
        raise MutatingTransportError("no local agent lineage", code="UNKNOWN_WORKER")


def select_mutating_backend_name() -> WorkerBackendType:
    import os

    if os.environ.get("CURSOR_API_KEY"):
        return WorkerBackendType.CLOUD_API
    if which("agent") is not None or which("cursor-agent") is not None:
        return WorkerBackendType.LOCAL_AGENT
    return WorkerBackendType.NONE
