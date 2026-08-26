"""AS-WEB-001 read-first web API adapters.

Read-only vault / OBS consumers for the Atlas web shell. Never writes
canonical vault planes (``projects/``, ``state/``, claims, authority) and
never imports knowledge_compiler / ingestion writers.

Normative (ADR-008):
- UI ≠ canonical
- Graph ≠ authority
- Unknown ≠ healthy (absent OBS snapshot → unknown, never fabricated healthy)
"""

from __future__ import annotations

from project_atlas.web_api.brief import (
    WebBriefError,
    filter_knowledge_by_project,
    read_project_brief,
)
from project_atlas.web_api.conflicts import list_project_conflicts
from project_atlas.web_api.discovery import load_estate_discovery_view
from project_atlas.web_api.graph import impact_graph_summary, read_impact_graph
from project_atlas.web_api.health import (
    OBS_HEALTH_SNAPSHOT_RELATIVE,
    ReadStatus,
    VaultHealthView,
    read_status,
    read_vault_health,
)
from project_atlas.web_api.intelligence import (
    WebIntelligenceError,
    read_intelligence_conflicts,
    read_intelligence_evidence,
    read_intelligence_explain,
    read_intelligence_query,
    read_portfolio_state,
    read_project_attention,
    read_project_state,
)
from project_atlas.web_api.knowledge import KnowledgeAnswerSummary, list_knowledge_answers
from project_atlas.web_api.projects import ProjectSummary, list_projects
from project_atlas.web_api.roadmap import WebRoadmapError, read_project_roadmap
from project_atlas.web_api.source_health import (
    WebSourceHealthError,
    read_source_health,
)
from project_atlas.web_api.twin_read import (
    WebTwinReadError,
    read_twin_view,
    render_twin_text,
)

__all__ = [
    "OBS_HEALTH_SNAPSHOT_RELATIVE",
    "KnowledgeAnswerSummary",
    "ProjectSummary",
    "ReadStatus",
    "VaultHealthView",
    "WebBriefError",
    "WebIntelligenceError",
    "WebRoadmapError",
    "WebSourceHealthError",
    "WebTwinReadError",
    "filter_knowledge_by_project",
    "impact_graph_summary",
    "list_knowledge_answers",
    "list_project_conflicts",
    "list_projects",
    "load_estate_discovery_view",
    "read_impact_graph",
    "read_intelligence_conflicts",
    "read_intelligence_evidence",
    "read_intelligence_explain",
    "read_intelligence_query",
    "read_portfolio_state",
    "read_project_attention",
    "read_project_brief",
    "read_project_roadmap",
    "read_project_state",
    "read_source_health",
    "read_status",
    "read_twin_view",
    "read_vault_health",
    "render_twin_text",
]
