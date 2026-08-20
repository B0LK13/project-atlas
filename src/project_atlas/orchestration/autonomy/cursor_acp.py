"""Cursor ACP permission gate for governed local Agent workers.

Default REJECT. Atlas, not the worker, answers request_permission.
This module does not grant owner authority or merge rights.
"""

from __future__ import annotations

from typing import Literal

from project_atlas.orchestration.autonomy.mutating_transport import (
    MutatingLeaseBinding,
    command_is_forbidden,
    decide_acp_permission,
)


def handle_request_permission(
    kind: str,
    binding: MutatingLeaseBinding,
    *,
    command: str | None = None,
) -> Literal["ALLOW", "REJECT"]:
    """Broker-controlled ACP permission. Default REJECT."""
    if command is not None and command_is_forbidden(command):
        return "REJECT"
    return decide_acp_permission(kind, binding)
