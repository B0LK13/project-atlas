"""AS-2.1-APP-SVC-001 - shared application service layer.

Stable read-oriented facade over vault adapters for API / Web / MCP.
Never writes Layer B authority. Bound to Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.web_api import (
    impact_graph_summary,
    list_knowledge_answers,
    list_projects,
    read_status,
    read_vault_health,
)

PACKAGE_ID = "AS-2.1-APP-SVC-001"
TRUTH_BOUNDARY = "APP-SVC READ FACADE != AUTHORITY / != LIVE WRITE"


class AppServiceError(ValueError):
    """Fail-closed application service error."""


@dataclass(frozen=True, slots=True)
class AppService:
    """Vault-scoped application service (read-first)."""

    vault: Path
    package_id: str = PACKAGE_ID

    def __post_init__(self) -> None:
        require_compatibility_anchor()
        if not self.vault.is_dir():
            raise AppServiceError("app-svc-vault-missing")

    def health(self) -> dict[str, Any]:
        status = read_status(self.vault)
        view = read_vault_health(self.vault)
        return {
            "package_id": PACKAGE_ID,
            "truth_boundary": TRUTH_BOUNDARY,
            "read_status": status,
            "vault_health": view,
        }

    def projects(self) -> list[dict[str, Any]]:
        return [dict(row) for row in list_projects(self.vault)]

    def knowledge(self) -> list[dict[str, Any]]:
        return [dict(row) for row in list_knowledge_answers(self.vault)]

    def graph_summary(self) -> dict[str, Any]:
        summary = impact_graph_summary(self.vault)
        out = dict(summary)
        out["authority"] = "derived"
        return out

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "truth_boundary": TRUTH_BOUNDARY,
            "health": self.health(),
            "projects": self.projects(),
            "knowledge": self.knowledge(),
            "graph": self.graph_summary(),
            "generated": {"by": "project-atlas"},
        }


def open_app_service(vault: Path) -> AppService:
    """Open a read-first application service for a vault root."""
    return AppService(vault=vault.resolve())
