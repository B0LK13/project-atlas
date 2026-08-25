"""AS-2.1-APP-SVC-001 - shared application service layer.

Stable read-oriented facade over vault adapters for API / Web / MCP.
Never writes Layer B authority. Bound to Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import require_compatibility_anchor
from project_atlas.knowledge_diff import (
    KnowledgeDiffError,
    diff_knowledge,
    read_as_of,
)
from project_atlas.web_api import (
    WebAttentionError,
    WebBriefError,
    WebChangedError,
    WebDecisionsError,
    WebInboxError,
    WebIntelligenceError,
    WebOverviewError,
    WebRoadmapError,
    WebSourceHealthError,
    WebStateError,
    WebUnknownError,
    filter_knowledge_by_project,
    impact_graph_summary,
    list_knowledge_answers,
    list_project_conflicts,
    list_projects,
    load_estate_discovery_view,
    read_intelligence_conflicts,
    read_intelligence_evidence,
    read_intelligence_explain,
    read_intelligence_query,
    read_portfolio_state,
    read_project_attention,
    read_project_attention_hygiene,
    read_project_brief,
    read_project_changed,
    read_project_current_state,
    read_project_decisions,
    read_project_inbox,
    read_project_overview,
    read_project_roadmap,
    read_project_state,
    read_project_unknown,
    read_source_health,
    read_status,
    read_vault_health,
)

PACKAGE_ID = "AS-2.1-APP-SVC-001"
TRUTH_BOUNDARY = "APP-SVC READ FACADE != AUTHORITY / != LIVE WRITE"


class AppServiceError(ValueError):
    """Fail-closed application service error."""

    honesty: str | None = None


def _intel_error(exc: WebIntelligenceError) -> AppServiceError:
    error = AppServiceError(str(exc))
    error.honesty = exc.honesty.value
    return error


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

    def estate_discovery(self) -> dict[str, Any]:
        """D-049 read-only estate discovery projection (never invents roots)."""
        return load_estate_discovery_view(self.vault)

    def knowledge(self, project_id: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in list_knowledge_answers(self.vault)]
        try:
            return filter_knowledge_by_project(rows, project_id)
        except WebBriefError as exc:
            raise AppServiceError(str(exc)) from exc

    def brief(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha project brief + Truth UX projection (read-only)."""
        try:
            return read_project_brief(self.vault, project_id)
        except WebBriefError as exc:
            raise AppServiceError(str(exc)) from exc

    def roadmap(self, project_id: str) -> dict[str, Any]:
        """Living Project Roadmap V1 (read-only; ROADMAP != canonical)."""
        try:
            return read_project_roadmap(self.vault, project_id)
        except WebRoadmapError as exc:
            raise AppServiceError(str(exc)) from exc

    def source_health(self, project_id: str) -> dict[str, Any]:
        """Project-scoped source-health lens (read-only; != authority)."""
        try:
            return read_source_health(self.vault, project_id)
        except WebSourceHealthError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def unknown(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha unknown/conflict lens (read-only; UNKNOWN != healthy)."""
        try:
            return read_project_unknown(self.vault, project_id)
        except WebUnknownError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def changed(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha What Changed lens (read-only; != kdiff authority)."""
        try:
            return read_project_changed(self.vault, project_id)
        except WebChangedError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def inbox(
        self,
        project_id: str,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Coder Alpha inbox list (read-only; listing != mutation != command)."""
        try:
            return read_project_inbox(
                self.vault, project_id, status=status, limit=limit
            )
        except WebInboxError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def overview(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha project overview (read-only; != Layer B authority)."""
        try:
            return read_project_overview(self.vault, project_id)
        except WebOverviewError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def decisions(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha decision memory (read-only; != governing authority)."""
        try:
            return read_project_decisions(self.vault, project_id)
        except WebDecisionsError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def attention(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha attention hygiene (read-only; != /v1/project-attention)."""
        try:
            return read_project_attention_hygiene(self.vault, project_id)
        except WebAttentionError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def state(self, project_id: str) -> dict[str, Any]:
        """Coder Alpha current-state lens (read-only; != /v1/project-state)."""
        try:
            return read_project_current_state(self.vault, project_id)
        except WebStateError as exc:
            error = AppServiceError(str(exc))
            error.honesty = exc.honesty
            raise error from exc

    def graph_summary(self) -> dict[str, Any]:
        summary = impact_graph_summary(self.vault)
        out = dict(summary)
        out["authority"] = "derived"
        return out

    def conflicts(self, project_id: str) -> dict[str, Any]:
        """Unresolved conflicts for one project (read-only; no resolution)."""
        try:
            return list_project_conflicts(self.vault, project_id)
        except ValueError as exc:
            raise AppServiceError(str(exc)) from exc

    def kdiff_as_of(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Time Machine as-of read (AS-2.2-KDIFF-001; read-only, ≠ authority)."""
        try:
            return read_as_of(
                self.vault, project_id=project_id, as_of_valid_time=as_of
            )
        except KnowledgeDiffError as exc:
            raise AppServiceError(str(exc)) from exc

    def kdiff_diff(self, project_id: str, t1: str, t2: str) -> dict[str, Any]:
        """Time Machine T1→T2 diff (AS-2.2-KDIFF-001; read-only, ≠ authority)."""
        try:
            return diff_knowledge(self.vault, project_id=project_id, t1=t1, t2=t2)
        except KnowledgeDiffError as exc:
            raise AppServiceError(str(exc)) from exc

    def intelligence_evidence(
        self,
        project_id: str,
        *,
        subject: str | None = None,
        field: str | None = None,
        claim_id: str | None = None,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_intelligence_evidence(
                self.vault,
                project_id,
                subject=subject,
                field=field,
                claim_id=claim_id,
                as_of_valid_time=as_of_valid_time,
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def intelligence_conflicts(
        self,
        project_id: str,
        *,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_intelligence_conflicts(
                self.vault, project_id, as_of_valid_time=as_of_valid_time
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def intelligence_explain(
        self,
        project_id: str,
        *,
        subject: str | None = None,
        field: str | None = None,
        claim_id: str | None = None,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_intelligence_explain(
                self.vault,
                project_id,
                subject=subject,
                field=field,
                claim_id=claim_id,
                as_of_valid_time=as_of_valid_time,
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def project_state(
        self,
        project_id: str,
        *,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_project_state(
                self.vault, project_id, as_of_valid_time=as_of_valid_time
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def project_attention(
        self,
        project_id: str,
        *,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_project_attention(
                self.vault, project_id, as_of_valid_time=as_of_valid_time
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def portfolio_state(
        self,
        project_ids: tuple[str, ...] = (),
        *,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_portfolio_state(
                self.vault, project_ids, as_of_valid_time=as_of_valid_time
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

    def intelligence_query(
        self,
        project_id: str,
        kind: str,
        *,
        subject: str | None = None,
        field: str | None = None,
        claim_id: str | None = None,
        as_of_valid_time: str | None = None,
    ) -> dict[str, Any]:
        try:
            return read_intelligence_query(
                self.vault,
                project_id,
                kind,
                subject=subject,
                field=field,
                claim_id=claim_id,
                as_of_valid_time=as_of_valid_time,
            )
        except WebIntelligenceError as exc:
            raise _intel_error(exc) from exc

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
