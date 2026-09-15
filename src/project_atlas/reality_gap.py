"""AS-2.0-REALITY-GAP-001 — fixture inventory for Atlas 1.0→2.0 reality gaps.

Fixtures only. Does not invent estate/PILOT roots, does not stamp WEB ACCEPTED,
RELEASE, or 2.0 READY. Bound to the Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-REALITY-GAP-001"

GapStatus = Literal[
    "open",
    "partially-addressed",
    "blocked-pilot",
    "blocked-freeze",
    "addressed-fixture-only",
]


@dataclass(frozen=True, slots=True)
class RealityGapScenario:
    gap_id: str
    title: str
    one_dot_oh_today: str
    two_dot_oh_aspiration: str
    blocker: str
    status: GapStatus
    notes: str | None = None


# Canonical catalog mirrored from docs/atlas-2.0/REALITY-GAP.md (fixtures only).
CANONICAL_GAPS: tuple[RealityGapScenario, ...] = (
    RealityGapScenario(
        gap_id="estate-twin",
        title="Estate twin",
        one_dot_oh_today="fixtures only; PILOT_ROOTS=0",
        two_dot_oh_aspiration="Digital Twin",
        blocker="PILOT / waiver",
        status="blocked-pilot",
        notes="Fixture twin ≠ authentic estate PILOT PASSED",
    ),
    RealityGapScenario(
        gap_id="agent-os-in-core",
        title="Agent OS in Core",
        one_dot_oh_today="sibling control plane",
        two_dot_oh_aspiration="integrated Agent OS",
        blocker="owner auth + READY",
        status="partially-addressed",
        notes="AS-2.0-AGENTOS-001 envelope is complementary; not Core absorption",
    ),
    RealityGapScenario(
        gap_id="federation",
        title="Federation",
        one_dot_oh_today="XPROJ derived only",
        two_dot_oh_aspiration="multi-vault FED",
        blocker="contract freeze",
        status="partially-addressed",
        notes="AS-2.0-FED-001 join inventory is consume-only",
    ),
    RealityGapScenario(
        gap_id="advanced-ux",
        title="Advanced UX",
        one_dot_oh_today="WEB ACCEPTED cleared on tip",
        two_dot_oh_aspiration="UX-001 advanced CC",
        blocker="WEB governor #10 (cleared for entry)",
        status="partially-addressed",
        notes="AS-2.0-UX-001 entry gate; UI≠canonical preserved",
    ),
    RealityGapScenario(
        gap_id="production-sync",
        title="Production SYNC",
        one_dot_oh_today="dry-run scaffolds",
        two_dot_oh_aspiration="SYNC v2",
        blocker="PILOT + INT-013",
        status="blocked-pilot",
        notes="Fixture waiver insufficient for 2.0 SYNC final",
    ),
    RealityGapScenario(
        gap_id="provider-mcp",
        title="Provider/MCP",
        one_dot_oh_today="design PROTOTYPE / optional registry",
        two_dot_oh_aspiration="optional adapters",
        blocker="NFR-006 + freeze",
        status="partially-addressed",
        notes="AS-2.0-PROV-001 registry disabled-by-default; no SDK wiring",
    ),
)


class RealityGapError(ValueError):
    """Fail-closed reality-gap inventory error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _scenario_dict(scenario: RealityGapScenario) -> dict[str, Any]:
    item: dict[str, Any] = {
        "gap_id": scenario.gap_id,
        "title": scenario.title,
        "one_dot_oh_today": scenario.one_dot_oh_today,
        "two_dot_oh_aspiration": scenario.two_dot_oh_aspiration,
        "blocker": scenario.blocker,
        "status": scenario.status,
        "evidence_class": "fixture-only",
        "authentic_estate": False,
        "invent_pilot_roots": False,
    }
    if scenario.notes:
        item["notes"] = scenario.notes
    return item


def build_reality_gap_inventory(
    vault: Path,
    *,
    scenarios: tuple[RealityGapScenario, ...] | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Write a deterministic reality-gap fixture inventory (no estate invent)."""
    verified = anchor or require_compatibility_anchor()
    items = list(scenarios) if scenarios is not None else list(CANONICAL_GAPS)
    if not items:
        raise RealityGapError("reality-gap-empty")

    seen: set[str] = set()
    serialized: list[dict[str, Any]] = []
    for scenario in items:
        gid = scenario.gap_id.strip()
        if not gid or gid in seen:
            raise RealityGapError(f"reality-gap-id-invalid-or-duplicate:{gid}")
        seen.add(gid)
        serialized.append(_scenario_dict(scenario))

    serialized.sort(key=lambda item: item["gap_id"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "source_doc": "docs/atlas-2.0/REALITY-GAP.md",
        "pilot_roots": 0,
        "authentic_estate_pilot_passed": verified.authentic_estate_pilot_passed,
        "scenarios": serialized,
        "scenario_count": len(serialized),
        "authority": {
            "level": "derived",
            "note": "Fixture inventory only; never invents estate or stamps release",
        },
        "truth_boundary": (
            "REALITY-GAP FIXTURE ≠ PILOT PASS / ≠ WEB ACCEPTED / ≠ 2.0 RELEASE"
        ),
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "reality-gap-inventory")
    except SchemaValidationError as exc:
        raise RealityGapError(f"reality-gap-schema:{exc}") from exc

    out = vault.resolve() / "generated" / "ops" / "reality-gap-inventory.json"
    _atomic_write_json(out, payload)
    return payload
