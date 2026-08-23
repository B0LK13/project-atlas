"""AS-CODER-ALPHA-DEMO-READINESS-001 — derived demo-journey classifier.

Aggregates landed Atlas contracts. This module is not a truth engine.

Honesty (must appear on every receipt):
  DEMO_FIXTURE != AUTHENTIC_PILOT
  DEMO != RELEASE
  UI != CANONICAL_TRUTH
  MODEL_OUTPUT != AUTHORITY
  MISSING != PASS

Never emits RELEASE or COMMERCIAL_GA. Does not duplicate discovery,
inventory-drift, or Next ranking.
"""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.agent_handoff import create_handoff, export_agent_context
from project_atlas.attention_hygiene import classify_attention
from project_atlas.connect import connect_project
from project_atlas.inventory_drift import evaluate_connect_inventory_drift
from project_atlas.obsidian_projection import materialize_obsidian_projection
from project_atlas.overview import build_overview_lens
from project_atlas.project_architecture import build_architecture_lens
from project_atlas.project_brief import build_project_brief
from project_atlas.project_changed import materialize_changed_lenses
from project_atlas.project_decisions import build_decisions_lens
from project_atlas.project_next import build_next_lens
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_health import explain_source_health

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-DEMO-READINESS-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-demo-readiness-001"
StageState = Literal["READY", "PARTIAL", "BLOCKED", "UNKNOWN", "NOT_IMPLEMENTED"]
JOURNEY: Final[tuple[str, ...]] = (
    "project_root",
    "connect_discover",
    "project_identity",
    "source_inventory",
    "drift_state",
    "overview",
    "architecture",
    "next",
    "state_attention_decisions",
    "inbox",
    "api_cli_web",
)
HONESTY = {
    "demo_fixture_is_authentic_pilot": False,
    "demo_is_release": False,
    "ui_is_canonical_truth": False,
    "model_output_is_authority": False,
    "commercial_ga": False,
    "authentic_pilot": False,
    "demo_readiness_is_derived": True,
    "demo_readiness_is_authority": False,
    "missing_is_pass": False,
}
STAMPS = (
    "DEMO_FIXTURE != AUTHENTIC_PILOT",
    "DEMO != RELEASE",
    "UI != CANONICAL_TRUTH",
    "MODEL_OUTPUT != AUTHORITY",
    "MISSING != PASS",
)
NEXT_API_STATUS: Final[str] = "PENDING_OWNER_HELD_406"
LIVE_API_PRESENT: Final[tuple[str, ...]] = (
    "/v1/ask",
    "/v1/projects",
    "/v1/discovery",
    "/v1/knowledge",
    "/v1/brief",
    "/v1/roadmap",
    "/v1/source-health",
    "/v1/project-state",
    "/v1/conflicts",
    "/v1/kdiff",
)


class DemoReadinessError(ValueError):
    """Fail-closed demo-readiness error."""


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _inbox_list_available() -> bool:
    module = importlib.import_module("project_atlas.knowledge_inbox")
    return callable(getattr(module, "list_inbox_items", None))


def _stage(name: str, state: StageState, *, note: str) -> dict[str, Any]:
    if state not in {"READY", "PARTIAL", "BLOCKED", "UNKNOWN", "NOT_IMPLEMENTED"}:
        raise DemoReadinessError(f"invalid stage state: {state}")
    return {"name": name, "state": state, "note": note}


def _rollup(stages: list[dict[str, Any]]) -> str:
    states = [str(item["state"]) for item in stages]
    if "BLOCKED" in states:
        return "BLOCKED"
    if "UNKNOWN" in states:
        return "PARTIAL"
    if any(state in {"PARTIAL", "NOT_IMPLEMENTED"} for state in states):
        return "PARTIAL"
    if states and all(state == "READY" for state in states):
        return "PASS"
    return "PARTIAL"


def run_demo_readiness(
    harbor_src: Path,
    *,
    work_root: Path,
    decoy_name: str = "portal-app",
) -> dict[str, Any]:
    """Connect harbor + a decoy project; classify the current-main journey."""
    harbor_src = harbor_src.expanduser().resolve()
    if not harbor_src.is_dir():
        raise DemoReadinessError(f"harbor source is not a directory: {harbor_src}")
    work_root = work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    harbor = work_root / "harbor-api"
    decoy = work_root / decoy_name
    if harbor.exists():
        shutil.rmtree(harbor)
    shutil.copytree(harbor_src, harbor)
    decoy.mkdir(parents=True, exist_ok=True)
    (decoy / "README.md").write_text(
        "# Portal App\n\nDecoy sibling for isolation. Not Harbor.\n",
        encoding="utf-8",
    )

    first = connect_project(harbor)
    vault = Path(str(first["vault"]))
    second = connect_project(harbor)
    harbor_id = str(first.get("bound_project_id") or "")
    # D-050 last-writer: connect-manifest.json is a single-root commit.
    # Classify harbor inventory/drift against harbor's committed manifest
    # before the decoy overwrite (isolation still uses the shared vault).
    manifest = vault / "generated" / "ops" / "connect-manifest.json"
    inventory_present = manifest.is_file()
    drift = evaluate_connect_inventory_drift(vault, harbor_id)
    decoy_report = connect_project(decoy, vault=vault)
    decoy_id = str(decoy_report.get("bound_project_id") or decoy_name)

    overview = build_overview_lens(vault, harbor_id)
    architecture = build_architecture_lens(vault, harbor_id)
    state = build_state_lens(vault, harbor_id)
    changed = materialize_changed_lenses(vault, project_ids=[harbor_id])
    decisions = build_decisions_lens(vault, harbor_id)
    unknown = build_unknown_lens(vault, harbor_id)
    attention = classify_attention(vault, harbor_id)
    health = explain_source_health(vault, harbor_id)
    nxt = build_next_lens(vault, harbor_id)
    brief = build_project_brief(vault, harbor_id, refresh=False)
    context = export_agent_context(vault, harbor_id, refresh_brief=False)
    handoff = create_handoff(vault, harbor_id, note="demo-readiness", refresh_brief=False)
    obsidian = materialize_obsidian_projection(
        vault, project_id=harbor_id, refresh_brief=False
    )
    decoy_health = explain_source_health(vault, decoy_id)
    decoy_ctx = export_agent_context(vault, decoy_id, refresh_brief=False)

    dumped_harbor = _dump(
        {
            "overview": overview,
            "state": state,
            "changed": changed,
            "decisions": decisions,
            "unknown": unknown,
            "attention": attention,
            "health": health,
            "next": nxt,
            "brief": brief,
            "context": context,
            "handoff": handoff,
            "architecture": architecture,
            "drift": drift,
        }
    )
    leaked = decoy_id in dumped_harbor and "portal" in dumped_harbor.lower()
    decoy_dump = _dump({"ctx": decoy_ctx, "health": decoy_health})
    harbor_in_decoy = harbor_id in decoy_dump and "postgresql" in decoy_dump.lower()
    leak_count = 0 if not (leaked or harbor_in_decoy) else 1

    drift_status = str(drift.get("status") or "UNKNOWN")
    arch_status = str(architecture.get("status") or "unknown")
    inbox_available = _inbox_list_available()

    stages = [
        _stage(
            "project_root",
            "READY" if harbor.is_dir() else "BLOCKED",
            note="copied harbor fixture root",
        ),
        _stage(
            "connect_discover",
            "READY"
            if first.get("status") == "connected" and second.get("status") == "connected"
            else "BLOCKED",
            note="atlas connect + discover inventory on current main",
        ),
        _stage(
            "project_identity",
            "READY"
            if harbor_id
            and first.get("bound_project_id") == second.get("bound_project_id")
            else "BLOCKED",
            note="persistent bound_project_id; reconnect does not mint a new identity",
        ),
        _stage(
            "source_inventory",
            "READY" if inventory_present else "UNKNOWN",
            note="consumes connect-manifest; does not re-discover",
        ),
        _stage(
            "drift_state",
            "READY" if drift_status in {"FRESH", "STALE"} else "UNKNOWN",
            note=(
                f"consumes inventory_drift ({drift_status}); "
                "not a second source-drift engine"
            ),
        ),
        _stage(
            "overview",
            "READY" if overview else "UNKNOWN",
            note="derived overview lens; UI != canonical truth",
        ),
        _stage(
            "architecture",
            "READY" if arch_status == "derived" else "PARTIAL",
            note=f"architecture lens status={arch_status}; README is not architecture authority",
        ),
        _stage(
            "next",
            "PARTIAL" if nxt else "UNKNOWN",
            note=(
                "CLI/lens next exists on live main; "
                f"NEXT_API={NEXT_API_STATUS}; does not duplicate the Next engine"
            ),
        ),
        _stage(
            "state_attention_decisions",
            "READY" if state and attention and decisions else "PARTIAL",
            note="state / attention / decisions lenses on live main",
        ),
        _stage(
            "inbox",
            "READY" if inbox_available else "NOT_IMPLEMENTED",
            note=(
                "inbox list surface present on this runtime"
                if inbox_available
                else "inbox list is absent on live main; listing != mutation != command"
            ),
        ),
        _stage(
            "api_cli_web",
            "PARTIAL",
            note=(
                "CLI + LIVE_API + web presentation exist; "
                f"NEXT_API={NEXT_API_STATUS}; /v1/inbox=NOT_IMPLEMENTED; "
                "UI != canonical truth"
            ),
        ),
    ]

    checks = {
        "persistent_identity": first.get("projects") == second.get("projects")
        and first.get("bound_project_id") == second.get("bound_project_id"),
        "second_session_continuity": second.get("vault_created") is False
        and Path(str(second["vault"])) == vault,
        "overview_present": bool(overview),
        "architecture_derived": arch_status == "derived",
        "state_present": bool(state),
        "changed_present": bool(changed),
        "decisions_present": bool(decisions),
        "unknown_honest": "unknown" in _dump(unknown).lower()
        or "conflict" in _dump(unknown).lower(),
        "attention_present": bool(attention),
        "next_lens_present": bool(nxt),
        "brief_present": bool(brief),
        "context_present": bool(
            context.get("markdown")
            or context.get("markdown_path")
            or context.get("path")
        ),
        "handoff_present": bool(handoff.get("handoff_id") or handoff.get("path")),
        "obsidian_present": bool(obsidian.get("notes_written") or obsidian.get("receipt_path")),
        "drift_consumed": drift.get("package") == "AS-CODER-ALPHA-INVENTORY-DRIFT-001",
        "inbox_list_implemented": inbox_available,
        "next_api_landed": False,
        "cross_project_leak_count": leak_count,
    }
    failed = [
        name
        for name, ok in checks.items()
        if name not in {"cross_project_leak_count", "inbox_list_implemented", "next_api_landed"}
        and not ok
    ]
    if leak_count != 0:
        failed.append("cross_project_isolation")

    demo_status = _rollup(stages)
    if leak_count != 0 and demo_status != "BLOCKED":
        demo_status = "BLOCKED"
        stages.append(
            _stage(
                "isolation",
                "BLOCKED",
                note="cross-project leak detected; demo journey cannot pass",
            )
        )

    return {
        "schema_version": 1,
        "package": PACKAGE_ID,
        "status": demo_status,
        "demo_readiness": demo_status,
        "pilot_readiness": "NOT_IMPLEMENTED",
        "release_readiness": "NOT_IMPLEMENTED",
        "harbor_project_id": harbor_id,
        "decoy_project_id": decoy_id,
        "vault": vault.as_posix(),
        "journey": JOURNEY,
        "stages": stages,
        "checks": checks,
        "failed_checks": failed,
        "live_api_present": list(LIVE_API_PRESENT),
        "next_api": NEXT_API_STATUS,
        "inbox_list": "READY" if inbox_available else "NOT_IMPLEMENTED",
        "stamps": list(STAMPS),
        "honesty": dict(HONESTY),
        "truth_boundary": " ; ".join(STAMPS),
        "generated": {"by": GENERATOR_ID},
    }
