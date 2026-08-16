"""Shim — canonical receipt validate/issue live in project_atlas.agent_control.receipt_gate."""

from project_atlas.agent_control.receipt_gate import issue, validate

__all__ = ["issue", "validate"]
