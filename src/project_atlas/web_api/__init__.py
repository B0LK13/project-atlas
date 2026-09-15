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

from project_atlas.web_api.architecture_read import (
    WebArchitectureReadError,
    read_architecture_view,
)
from project_atlas.web_api.bitemporal_read import (
    WebBitemporalReadError,
    read_bitemporal_view,
)
from project_atlas.web_api.brief import (
    WebBriefError,
    filter_knowledge_by_project,
    read_project_brief,
)
from project_atlas.web_api.changed_read import WebChangedReadError, read_changed_view
from project_atlas.web_api.conflicts import list_project_conflicts
from project_atlas.web_api.decisions_read import (
    WebDecisionsReadError,
    read_decisions_view,
)
from project_atlas.web_api.discovery import load_estate_discovery_view
from project_atlas.web_api.graph import impact_graph_summary, read_impact_graph
from project_atlas.web_api.health import (
    OBS_HEALTH_SNAPSHOT_RELATIVE,
    ReadStatus,
    VaultHealthView,
    read_status,
    read_vault_health,
)
from project_atlas.web_api.index_status import WebIndexStatusError, read_index_status
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
from project_atlas.web_api.next_read import WebNextReadError, read_next_view
from project_atlas.web_api.overview_read import WebOverviewReadError, read_overview_view
from project_atlas.web_api.portfolio_read import WebPortfolioReadError, read_portfolio_view
from project_atlas.web_api.projects import ProjectSummary, list_projects
from project_atlas.web_api.roadmap import WebRoadmapError, read_project_roadmap
from project_atlas.web_api.roadmap_read import (
    WebRoadmapAnswersReadError,
    read_roadmap_answers_view,
)
from project_atlas.web_api.source_health import (
    WebSourceHealthError,
    read_source_health,
)
from project_atlas.web_api.state_read import WebStateReadError, read_state_view
from project_atlas.web_api.unknown_read import WebUnknownReadError, read_unknown_view

__all__ = [
    "OBS_HEALTH_SNAPSHOT_RELATIVE",
    "KnowledgeAnswerSummary",
    "ProjectSummary",
    "ReadStatus",
    "VaultHealthView",
    "WebArchitectureReadError",
    "WebBitemporalReadError",
    "WebBriefError",
    "WebChangedReadError",
    "WebDecisionsReadError",
    "WebIndexStatusError",
    "WebIntelligenceError",
    "WebNextReadError",
    "WebOverviewReadError",
    "WebPortfolioReadError",
    "WebRoadmapAnswersReadError",
    "WebRoadmapError",
    "WebSourceHealthError",
    "WebStateReadError",
    "WebUnknownReadError",
    "filter_knowledge_by_project",
    "impact_graph_summary",
    "list_knowledge_answers",
    "list_project_conflicts",
    "list_projects",
    "load_estate_discovery_view",
    "read_architecture_view",
    "read_bitemporal_view",
    "read_changed_view",
    "read_decisions_view",
    "read_impact_graph",
    "read_index_status",
    "read_intelligence_conflicts",
    "read_intelligence_evidence",
    "read_intelligence_explain",
    "read_intelligence_query",
    "read_next_view",
    "read_overview_view",
    "read_portfolio_state",
    "read_portfolio_view",
    "read_project_attention",
    "read_project_brief",
    "read_project_roadmap",
    "read_project_state",
    "read_roadmap_answers_view",
    "read_source_health",
    "read_state_view",
    "read_status",
    "read_unknown_view",
    "read_vault_health",
]
