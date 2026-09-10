"""AS-WORK-READINESS-001 — derived work-queue projection and handoff prep.

ATLAS-WORK-READINESS-AND-HANDOFF-001.

This package **advises** and prepares transfer packets. It does not assign,
dispatch, claim work, raise limits, or grant authorization.

Truth boundaries held here:

* ``PROJECTION != AUTHORITY``
* ``TECHNICALLY_READY != LAUNCH_AUTHORIZED``
* ``WORKER_EXIT_ZERO != TASK_COMPLETE``
* ``ACCEPTANCE_PASSED != INDEPENDENT_REVIEW``
* ``UNKNOWN_OWNER != AVAILABLE``
* ``FIXTURE_ADAPTER != LIVE_INTEGRATION``
* ``HAND OFF_PROPOSAL != CLAIM``
"""

from __future__ import annotations

from typing import Final, Literal

from project_atlas.orchestration.work_readiness.handoff import (
    prepare_handoff,
    refresh_handoff,
)
from project_atlas.orchestration.work_readiness.models import (
    Blocker,
    BlockerCode,
    HandoffProposal,
    ReadinessAxes,
    SelectionBucket,
    WorkItemProjection,
    WorkQueueReport,
)
from project_atlas.orchestration.work_readiness.project import project_queue
from project_atlas.orchestration.work_readiness.select import explain_item, select_next

PACKAGE_ID: Final[Literal["AS-WORK-READINESS-001"]] = "AS-WORK-READINESS-001"
SCHEMA_VERSION: Final[Literal[1]] = 1

__all__ = [
    "PACKAGE_ID",
    "SCHEMA_VERSION",
    "Blocker",
    "BlockerCode",
    "HandoffProposal",
    "ReadinessAxes",
    "SelectionBucket",
    "WorkItemProjection",
    "WorkQueueReport",
    "explain_item",
    "prepare_handoff",
    "project_queue",
    "refresh_handoff",
    "select_next",
]
