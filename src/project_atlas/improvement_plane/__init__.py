"""AS-IMPR-PLANE-001 — read-only delivery-evidence improvement plane.

Consumes existing Atlas development evidence (``docs/evidence`` JSON and
optional vault ops receipts) and produces a machine-readable report plus a
concise operator summary.

Recommendations cite source records, state uncertainty, and propose actions.
They grant no authority and never dispatch, retry, merge, or reprioritize.
"""

from __future__ import annotations

from project_atlas.improvement_plane.report import (
    PACKAGE_ID,
    SCHEMA_ID,
    TRUTH_BOUNDARY,
    compile_improvement_report,
    render_markdown_summary,
)

__all__ = [
    "PACKAGE_ID",
    "SCHEMA_ID",
    "TRUTH_BOUNDARY",
    "compile_improvement_report",
    "render_markdown_summary",
]
