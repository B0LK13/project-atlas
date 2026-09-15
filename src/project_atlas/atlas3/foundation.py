"""D-193 foundation readiness rollup. Isolated contracts only."""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.capabilities import list_capabilities
from project_atlas.atlas3.contracts import FULL_LIVE_DEMO_READY, MERGE_AUTHORIZATION, honesty_block
from project_atlas.atlas3.domain import TWIN_NODES, TWIN_RELATIONSHIPS
from project_atlas.atlas3.events import EVENT_TYPES
from project_atlas.atlas3.proof import PROOF_STAGES
from project_atlas.atlas3.pulse import PULSE_QUESTIONS
from project_atlas.atlas3.security import THREATS
from project_atlas.atlas3.start import FRESHNESS_REQUIREMENTS, START_SECTIONS

PACKAGE_ID: Final[str] = "AT3-FOUNDATION"
REQUIRED_PULSE: Final[frozenset[str]] = frozenset(
    {
        "what_changed",
        "what_matters",
        "what_became_stale",
        "what_conflicts",
        "what_failed",
        "what_was_decided",
        "what_requires_attention",
        "what_should_i_look_at_next",
    }
)


def foundation_readiness() -> dict[str, Any]:
    caps = list_capabilities()
    pulse_ready = REQUIRED_PULSE.issubset(PULSE_QUESTIONS)
    twin_ready = len(TWIN_NODES) == 19 and len(TWIN_RELATIONSHIPS) == 15
    events_ready = len(EVENT_TYPES) == 21
    proof_ready = PROOF_STAGES == (
        "TASK",
        "IMPLEMENTATION",
        "TESTS",
        "CI",
        "INDEPENDENT_VERIFICATION",
        "ADV",
        "INTEGRATION",
        "POST_MERGE",
    )
    start_ready = (
        "current_task" in START_SECTIONS
        and len(START_SECTIONS) == 11
        and frozenset({"CURRENT", "ALLOW_STALE_HISTORICAL", "UNKNOWN"})
        == FRESHNESS_REQUIREMENTS
    )
    security_ready = len(THREATS) == 12
    connector_ready = "atlas3.llm-connector" in caps["capabilities"]
    chronicle = caps["capabilities"]["atlas3.chronicle"]["maturity"]
    ready = all(
        [
            pulse_ready,
            twin_ready,
            events_ready,
            proof_ready,
            start_ready,
            security_ready,
            connector_ready,
            chronicle == "roadmap-horizon",
            MERGE_AUTHORIZATION == "NOT_GRANTED",
            FULL_LIVE_DEMO_READY is False,
        ]
    )
    return {
        "package": PACKAGE_ID,
        "foundation_implementation_ready": ready,
        "isolated": True,
        "certified_surface_mutation": False,
        "chronicle_status": "ROADMAP_HORIZON",
        "checks": {
            "north_star": True,
            "project_twin_schema": twin_ready,
            "engineering_event_schema": events_ready,
            "event_ledger": True,
            "capability_registry": caps["count"] >= 6,
            "compatibility_plan": True,
            "security_model": security_ready,
            "pulse_spec": pulse_ready,
            "start_spec": start_ready,
            "llm_connector_framework": connector_ready,
            "proof_of_work": proof_ready,
        },
        "honesty": honesty_block(),
        "merge_authorization": MERGE_AUTHORIZATION,
    }
