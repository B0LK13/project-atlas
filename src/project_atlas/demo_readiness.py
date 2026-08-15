"""AS-CODER-ALPHA-DEMO-READINESS-001 — end-to-end Coder Alpha demo acceptance.

Runs existing lenses against a controlled fixture. Telemetry / demo only.

Honesty (must appear on every receipt):
  DEMO_FIXTURE != AUTHENTIC_PILOT
  DEMO != RELEASE
  UI != CANONICAL_TRUTH
  MODEL_OUTPUT != AUTHORITY

Never emits RELEASE or COMMERCIAL_GA.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from project_atlas.agent_handoff import create_handoff, export_agent_context
from project_atlas.attention_hygiene import classify_attention
from project_atlas.connect import connect_project
from project_atlas.obsidian_projection import materialize_obsidian_projection
from project_atlas.overview import build_overview_lens
from project_atlas.project_brief import build_project_brief
from project_atlas.project_changed import materialize_changed_lenses
from project_atlas.project_decisions import build_decisions_lens
from project_atlas.project_next import build_next_lens
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_health import explain_source_health

PACKAGE_ID = "AS-CODER-ALPHA-DEMO-READINESS-001"
HONESTY = {
    "demo_fixture_is_authentic_pilot": False,
    "demo_is_release": False,
    "ui_is_canonical_truth": False,
    "model_output_is_authority": False,
    "commercial_ga": False,
    "authentic_pilot": False,
}
STAMPS = (
    "DEMO_FIXTURE != AUTHENTIC_PILOT",
    "DEMO != RELEASE",
    "UI != CANONICAL_TRUTH",
    "MODEL_OUTPUT != AUTHORITY",
)


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def run_demo_readiness(
    harbor_src: Path,
    *,
    work_root: Path,
    decoy_name: str = "portal-app",
) -> dict[str, Any]:
    """Connect harbor + a decoy project; score journey honesty (not GA)."""
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
    vault = Path(first["vault"])
    second = connect_project(harbor)
    decoy_report = connect_project(decoy, vault=vault)
    harbor_id = str(first.get("bound_project_id") or "harbor-api")
    decoy_id = str(decoy_report.get("bound_project_id") or decoy_name)

    overview = build_overview_lens(vault, harbor_id)
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
        }
    )
    leaked = decoy_id in dumped_harbor and "portal" in dumped_harbor.lower()
    decoy_dump = _dump({"ctx": decoy_ctx, "health": decoy_health})
    harbor_in_decoy = harbor_id in decoy_dump and "postgresql" in decoy_dump.lower()
    raw_honesty = health.get("honesty")
    health_honesty: dict[str, Any] = raw_honesty if isinstance(raw_honesty, dict) else {}
    health_not_authority = health.get("authority") in {None, "derived"} and (
        health_honesty.get("lens_is_authority") is not True
    )

    checks = {
        "persistent_identity": first.get("projects") == second.get("projects")
        and first.get("bound_project_id") == second.get("bound_project_id"),
        "second_session_continuity": second.get("vault_created") is False
        and Path(second["vault"]) == vault,
        "overview_present": bool(overview),
        "state_present": bool(state),
        "changed_present": bool(changed),
        "decisions_present": bool(decisions),
        "unknown_honest": "unknown" in _dump(unknown).lower()
        or "conflict" in _dump(unknown).lower(),
        "conflict_or_unknown_surfaced": "conflict" in dumped_harbor.lower()
        or "unknown" in dumped_harbor.lower()
        or "postgresql" in dumped_harbor.lower(),
        "attention_present": bool(attention),
        "source_health_derived": health.get("honesty", {}).get("lens_is_authority") is False
        if isinstance(health.get("honesty"), dict)
        else health.get("authority") in {None, "derived"}
        or "SOURCE HEALTH" in _dump(health),
        "next_present": bool(nxt),
        "brief_present": bool(brief),
        "context_present": bool(
            context.get("markdown")
            or context.get("markdown_path")
            or context.get("path")
        ),
        "handoff_present": bool(handoff.get("handoff_id") or handoff.get("path")),
        "obsidian_present": bool(obsidian.get("notes_written") or obsidian.get("receipt_path")),
        "source_health_not_authority": health_not_authority,
        "cross_project_leak_count": 0 if not (leaked or harbor_in_decoy) else 1,
    }
    failed = [name for name, ok in checks.items() if name != "cross_project_leak_count" and not ok]
    if checks["cross_project_leak_count"] != 0:
        failed.append("cross_project_isolation")
    status = "PASS" if not failed else "PARTIAL" if len(failed) <= 3 else "FAIL"
    return {
        "schema_version": 1,
        "package": PACKAGE_ID,
        "status": status,
        "demo_readiness": status,
        "harbor_project_id": harbor_id,
        "decoy_project_id": decoy_id,
        "vault": vault.as_posix(),
        "checks": checks,
        "failed_checks": failed,
        "stamps": list(STAMPS),
        "honesty": dict(HONESTY),
        "truth_boundary": " ; ".join(STAMPS),
        "generated": {"by": "atlas-coder-alpha-demo-readiness-001"},
    }
