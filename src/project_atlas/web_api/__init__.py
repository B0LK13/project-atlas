"""AS-WEB-001 read-first web API adapters.

Read-only vault / OBS consumers for the Atlas web shell. Never writes
canonical vault planes (``projects/``, ``state/``, claims, authority) and
never imports graph / knowledge_compiler writers.

Normative (ADR-008):
- UI ≠ canonical
- Graph ≠ authority
- Unknown ≠ healthy (absent OBS snapshot → unknown, never fabricated healthy)
"""

from __future__ import annotations

from project_atlas.web_api.health import (
    OBS_HEALTH_SNAPSHOT_RELATIVE,
    ReadStatus,
    VaultHealthView,
    read_status,
    read_vault_health,
)
from project_atlas.web_api.projects import ProjectSummary, list_projects

__all__ = [
    "OBS_HEALTH_SNAPSHOT_RELATIVE",
    "ProjectSummary",
    "ReadStatus",
    "VaultHealthView",
    "list_projects",
    "read_status",
    "read_vault_health",
]
