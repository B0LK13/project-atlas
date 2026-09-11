"""ATLAS-LIVE-COMPONENT-INTEGRATION-002 — live public-interface bridge.

Wires AS-TASK-CONTRACT-001 → AS-TASK-CONTEXT-AND-CONTINUITY-001 →
AS-WORK-READINESS-001 without copying authorization logic.

Truth boundaries:

* ``LIVE_BRIDGE != AUTHORITY``
* ``TECHNICALLY_VALID != EXECUTABLE``
* ``FIXTURE_LABELED`` paths are never silent production fallbacks
* ``INDEPENDENT_REVIEW`` / ``REAL_LAUNCH_AUTHORIZED`` are never granted here
"""

from __future__ import annotations

from typing import Final, Literal

from project_atlas.orchestration.live_integration.bridge import (
    IntegrationError,
    build_review_package,
    live_contract_to_context_snapshot,
    live_contract_to_readiness_view,
    project_from_live_contracts,
    run_controlled_chain,
)
from project_atlas.orchestration.live_integration.models import (
    ComponentManifest,
    IntegrationReport,
    ReviewPackage,
)

PACKAGE_ID: Final[Literal["AS-LIVE-COMPONENT-INTEGRATION-002"]] = (
    "AS-LIVE-COMPONENT-INTEGRATION-002"
)

__all__ = [
    "PACKAGE_ID",
    "ComponentManifest",
    "IntegrationError",
    "IntegrationReport",
    "ReviewPackage",
    "build_review_package",
    "live_contract_to_context_snapshot",
    "live_contract_to_readiness_view",
    "project_from_live_contracts",
    "run_controlled_chain",
]
