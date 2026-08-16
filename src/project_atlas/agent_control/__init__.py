"""Canonical Atlas agent-control primitives shared with the sibling control plane.

``session``, ``receipt_gate``, and ``postflight`` live here so Core and
``atlas-vault-documentation/agent_control`` call the same implementation.

CANONICAL_RECEIPT_VALIDATE_IMPLEMENTATIONS = 1
CANONICAL_RECEIPT_ISSUE_IMPLEMENTATIONS = 1
CANONICAL_RECEIPT_IS_AUTHORITY = NO
"""

from project_atlas.agent_control.postflight import run as postflight_run
from project_atlas.agent_control.receipt_gate import issue, validate

__all__ = ["issue", "postflight_run", "validate"]
