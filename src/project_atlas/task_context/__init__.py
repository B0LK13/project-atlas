"""ATLAS-TASK-CONTEXT-AND-CONTINUITY-001 — task-bound context packets.

Compose a compact, traceable, freshness-aware context packet for one task
contract. Extends existing Atlas context/provenance patterns; does not add
dispatch, authorization, a second search index, or an agent runtime.

Truth boundaries (enforced in the data model, not only as labels):

* ``POLICY`` comes from explicit configuration, never from retrieved text.
* ``TASK_REQUIREMENT`` comes from a validated contract snapshot.
* ``RETRIEVED`` is quoted evidence and cannot widen mutation scope, grant
  tools, or authorize execution.

``PACKET_SNAPSHOT != LIVE_ENVIRONMENT``.
``CONTINUATION_VIEW != RESUME_AUTHORIZATION``.
``AGENT_PROSE != EXECUTION_EVIDENCE``.
"""

from __future__ import annotations

from project_atlas.task_context.assemble import (
    TaskContextError,
    assemble_packet,
    check_freshness,
    compare_packets,
    render_view,
)
from project_atlas.task_context.models import (
    PACKAGE_ID,
    SCHEMA_VERSION,
    TRUTH_BOUNDARY,
    content_digest,
)

__all__ = [
    "PACKAGE_ID",
    "SCHEMA_VERSION",
    "TRUTH_BOUNDARY",
    "TaskContextError",
    "assemble_packet",
    "check_freshness",
    "compare_packets",
    "content_digest",
    "render_view",
]
