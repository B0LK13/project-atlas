"""AS-2.0-COMPAT-001 — 1.0 compatibility anchor consumer.

Loads and verifies the machine-readable Atlas 1.0 freeze pin. Atlas 2.0
packages must bind to this snapshot; 1.0 wins dependency conflicts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-COMPAT-001"
SNAPSHOT_ID = "atlas-1.0.0-compat"
EXPECTED_FREEZE_HEAD = "f4079813025dd882e0e3608ab7ad5b3b17f95bd9"
EXPECTED_FREEZE_TREE = "feb0441a13e391812ae07a1a8eb27b0de1061469"
EXPECTED_TAG = "v1.0.0"
EXPECTED_TAG_COMMIT = "bb0957c47b5e2976b5cf358342cf89dffe6e6a55"
RELATIVE_ANCHOR_PATH = Path("docs") / "releases" / "1.0.0" / "compatibility-anchor.json"


class CompatAnchorError(ValueError):
    """Raised when the compatibility anchor is missing or drifts."""


@dataclass(frozen=True, slots=True)
class CompatibilityAnchor:
    """Verified Atlas 1.0 compatibility snapshot."""

    snapshot_id: str
    package_version: str
    tag: str
    tag_commit: str
    software_freeze_head: str
    software_freeze_tree: str
    release_certified: bool
    pilot_mode: str
    authentic_estate_pilot_passed: bool
    one_dot_oh_wins_conflicts: bool
    invariants: tuple[str, ...]
    adr_manifest: tuple[str, ...]
    path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "schema": "compatibility-anchor",
            "snapshot_id": self.snapshot_id,
            "package_version": self.package_version,
            "tag": self.tag,
            "tag_commit": self.tag_commit,
            "software_freeze_head": self.software_freeze_head,
            "software_freeze_tree": self.software_freeze_tree,
            "release_certified": self.release_certified,
            "pilot_mode": self.pilot_mode,
            "authentic_estate_pilot_passed": self.authentic_estate_pilot_passed,
            "one_dot_oh_wins_conflicts": self.one_dot_oh_wins_conflicts,
            "invariants": list(self.invariants),
            "adr_manifest": list(self.adr_manifest),
            "generated": {"by": "project-atlas"},
        }


def default_anchor_path(repo_root: Path | None = None) -> Path:
    """Resolve the shipped compatibility-anchor.json path."""
    if repo_root is None:
        # src/project_atlas/compat_anchor.py → repo root
        repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / RELATIVE_ANCHOR_PATH).resolve()


def load_compatibility_anchor(path: Path | None = None) -> CompatibilityAnchor:
    """Load, schema-validate, and pin-check the 1.0 compatibility anchor."""
    anchor_path = path if path is not None else default_anchor_path()
    if not anchor_path.is_file():
        raise CompatAnchorError(f"compatibility-anchor-missing:{anchor_path}")
    try:
        payload = json.loads(anchor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompatAnchorError(f"compatibility-anchor-invalid-json:{exc}") from exc
    if not isinstance(payload, dict):
        raise CompatAnchorError("compatibility-anchor-not-object")
    try:
        validate_record(payload, "compatibility-anchor")
    except SchemaValidationError as exc:
        raise CompatAnchorError(f"compatibility-anchor-schema:{exc}") from exc

    head = str(payload["software_freeze_head"])
    tree = str(payload["software_freeze_tree"])
    tag = str(payload["tag"])
    tag_commit = str(payload["tag_commit"])
    if head != EXPECTED_FREEZE_HEAD:
        raise CompatAnchorError(f"compatibility-anchor-head-drift:{head}")
    if tree != EXPECTED_FREEZE_TREE:
        raise CompatAnchorError(f"compatibility-anchor-tree-drift:{tree}")
    if tag != EXPECTED_TAG:
        raise CompatAnchorError(f"compatibility-anchor-tag-drift:{tag}")
    if tag_commit != EXPECTED_TAG_COMMIT:
        raise CompatAnchorError(f"compatibility-anchor-tag-commit-drift:{tag_commit}")
    if payload.get("snapshot_id") != SNAPSHOT_ID:
        raise CompatAnchorError("compatibility-anchor-snapshot-id-drift")
    if payload.get("release_certified") is not True:
        raise CompatAnchorError("compatibility-anchor-not-certified")
    if payload.get("one_dot_oh_wins_conflicts") is not True:
        raise CompatAnchorError("compatibility-anchor-conflict-policy")

    return CompatibilityAnchor(
        snapshot_id=SNAPSHOT_ID,
        package_version=str(payload["package_version"]),
        tag=tag,
        tag_commit=tag_commit,
        software_freeze_head=head,
        software_freeze_tree=tree,
        release_certified=True,
        pilot_mode=str(payload["pilot_mode"]),
        authentic_estate_pilot_passed=bool(payload["authentic_estate_pilot_passed"]),
        one_dot_oh_wins_conflicts=True,
        invariants=tuple(str(item) for item in payload["invariants"]),
        adr_manifest=tuple(str(item) for item in payload["adr_manifest"]),
        path=anchor_path,
    )


def require_compatibility_anchor(path: Path | None = None) -> CompatibilityAnchor:
    """Fail-closed helper for 2.0 packages that must bind the 1.0 pin."""
    return load_compatibility_anchor(path)
