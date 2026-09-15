"""Globally unique agent and session identifiers."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


def agent_id(value: str | None, agent_type: str) -> str:
    candidate = value or agent_type
    if not SAFE.fullmatch(candidate):
        raise ValueError("unsafe agent id")
    return candidate


def session_id(agent: str, project_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"AS-{stamp}-{agent}-{project_id}-{secrets.token_hex(4)}"
