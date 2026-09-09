"""AS-STUDIO-A2-002 — Mission Journey RO vertical slice.

STUDIO_UI != AUTHORITY
KNOWLEDGE != PERMISSION
PREVIEW != EXECUTION
JOURNEY != MUTATION
A1_READ_ONLY = PRESERVED
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import cli as studio_cli  # noqa: E402
from atlas_studio import mission_control as mc  # noqa: E402
from atlas_studio import mission_journey as mj  # noqa: E402
from atlas_studio import snapshot as studio_snap  # noqa: E402

FIXED = "2026-09-09T15:00:00Z"
REPO = "B0LK13/project-atlas"


def clock():
    return FIXED


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _minimal_mc(*, freshness_state: str = "LIVE", repo: str | None = REPO) -> dict:
    """Injected MC-like packet for journey composition (presentation fixture)."""
    return {
        "schema": mc.SCHEMA_CONST,
        "generated_at_utc": FIXED,
        "repository": repo,
        "agent": "agent-alpha",
        "agent_status": "BOUND",
        "slice_status": "OK",
        "mission_status": "HEALTHY" if freshness_state == "LIVE" else "STALE",
        "snapshot_fingerprint": _fp("journey-mc"),
        "freshness": {"state": freshness_state, "max_age_seconds": 120},
        "honesty": mc.honesty_block(),
        "views": {"frontier": {"matrix": None, "frontier_fingerprint": _fp("front")}},
        "attention": {"items": [{"tier": 30, "title": "human gate"}]},
        "studio_snapshot": {
            "schema": studio_snap.SCHEMA_CONST,
            "slice_status": "OK",
            "repository": repo,
        },
        "observation_events": [],
        "provenance": {"notes": ["fixture"]},
    }


def _empty_listing() -> dict:
    return {
        "schema": "ATLAS_STUDIO_CLAIM_CANDIDATES_V1",
        "candidates": [],
        "notes": ["fixture"],
        "agent": "agent-alpha",
    }


def _listing_with_candidate() -> dict:
    return {
        "schema": "ATLAS_STUDIO_CLAIM_CANDIDATES_V1",
        "candidates": [
            {
                "lane": "pr/776",
                "pr": 776,
                "action_class": "OWNERSHIP_CLAIM",
                "ownership": "UNOWNED",
            }
        ],
        "notes": ["fixture"],
        "agent": "agent-alpha",
    }


def test_journey_schema_success_path():
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(),
        claim_listing=_listing_with_candidate(),
        knowledge_items=[
            {
                "path": "atlas-3/studio/REQUIREMENTS-REGISTER.md",
                "kind": "requirement",
                "title": "REQUIREMENTS-REGISTER",
                "provenance": {
                    "source_path": "atlas-3/studio/REQUIREMENTS-REGISTER.md",
                    "authority": False,
                },
            }
        ],
        clock=clock,
    )
    assert packet["schema"] == mj.SCHEMA_CONST
    assert packet["knowledge"]["state"] == mj.RETRIEVED
    assert packet["development"]["supported_capabilities"] == ["OWNERSHIP_CLAIM"]
    assert "CI_DISPATCH" in packet["development"]["closed_capabilities"]
    assert len(packet["next_actions"]["claim_candidates"]["candidates"]) == 1
    assert packet["honesty"]["journey_ne_mutation"] is True
    assert packet["honesty"]["knowledge_ne_permission"] is True
    assert packet["next_actions"]["preview"] is None
    assert mj.validate_mission_journey(packet) == []
    monitoring = packet["next_actions"]["monitoring"]
    assert monitoring["auto_retry"] is False
    assert "action-evidence" in monitoring["command"]
    task_ctx = packet["next_actions"]["task_context"]
    assert task_ctx["built_here"] is False
    assert task_ctx["ownership"] == "PR_786_DRAFT"
    assert "task-context" in task_ctx["command"]


def test_knowledge_none_found():
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(),
        claim_listing=_empty_listing(),
        knowledge_items=[],
        clock=clock,
    )
    assert packet["knowledge"]["state"] == mj.NONE_FOUND


def test_knowledge_unavailable_without_docs_root():
    k = mj.project_knowledge(docs_root=None, injected_items=None)
    assert k["state"] == mj.UNAVAILABLE


def test_knowledge_stale_when_mc_stale():
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(freshness_state="STALE"),
        claim_listing=_empty_listing(),
        knowledge_items=[{"path": "x.md", "kind": "mission_doc", "title": "x", "provenance": {}}],
        clock=clock,
    )
    assert packet["knowledge"]["state"] == mj.STALE
    assert "MC_FRESHNESS_STALE" in packet["knowledge"]["notes"]


def test_knowledge_incomplete_forced():
    k = mj.project_knowledge(force_state=mj.INCOMPLETE, injected_items=[{"path": "a"}])
    assert k["state"] == mj.INCOMPLETE


def test_docs_root_scan_retrieves_studio_docs(tmp_path):
    docs = tmp_path / "docs"
    target = docs / "atlas-3" / "studio"
    target.mkdir(parents=True)
    (target / "REQUIREMENTS-REGISTER.md").write_text("# reqs\n", encoding="utf-8")
    (docs / "adr").mkdir()
    (docs / "adr" / "ADR-035-studio-governed-action-intent.md").write_text(
        "# adr\n", encoding="utf-8"
    )
    k = mj.project_knowledge(docs_root=docs, max_items=12)
    assert k["state"] in {mj.RETRIEVED, mj.INCOMPLETE}
    assert any(i["kind"] == "requirement" for i in k["items"]) or any(
        "REQUIREMENTS" in i["path"] for i in k["items"]
    )


def test_development_missing_repo_prerequisite():
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(repo=None),
        claim_listing=_empty_listing(),
        knowledge_items=[],
        clock=clock,
    )
    assert "repository_identity" in packet["development"]["missing_prerequisites"]


def test_preview_attached_without_execution(monkeypatch):
    calls: list[str] = []

    def fake_preview(**kwargs):
        calls.append("preview")
        return {
            "schema": "ATLAS_STUDIO_ACTION_PREVIEW_V1",
            "action_type": "OWNERSHIP_CLAIM",
            "lane": kwargs.get("lane"),
            "would_mutate": False,
        }

    monkeypatch.setattr(
        "atlas_studio.action_intent.preview_ownership_claim",
        fake_preview,
    )
    # Also ensure execute is never imported/called via journey path.
    def boom_execute(*a, **k):
        raise AssertionError("execute must not run")

    monkeypatch.setattr(
        "atlas_studio.action_intent.execute_ownership_claim",
        boom_execute,
    )
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(),
        claim_listing=_listing_with_candidate(),
        knowledge_items=[],
        preview_lane="pr/776",
        clock=clock,
    )
    assert calls == ["preview"]
    assert packet["next_actions"]["preview"]["lane"] == "pr/776"
    assert packet["honesty"]["preview_ne_execution"] is True


def test_a1_mission_control_still_free_of_journey_and_governance():
    src = Path(mc.__file__).read_text(encoding="utf-8")
    for token in ("mission_journey", "governance", "action_intent", "emit_event"):
        assert token not in src, token


def test_cli_mission_journey_json(monkeypatch, capsys):
    fixed = mj.build_mission_journey(
        mission_control=_minimal_mc(),
        claim_listing=_empty_listing(),
        knowledge_items=[],
        clock=clock,
    )

    monkeypatch.setattr(
        "atlas_studio.mission_journey.build_mission_journey",
        lambda **kwargs: fixed,
    )
    rc = studio_cli.main(["mission-journey", "--json", "--no-docs"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == mj.SCHEMA_CONST
    assert out["honesty"]["journey_ne_mutation"] is True


def test_closed_capabilities_remain_closed():
    packet = mj.build_mission_journey(
        mission_control=_minimal_mc(),
        claim_listing=_empty_listing(),
        knowledge_items=[],
        clock=clock,
    )
    closed = set(packet["development"]["closed_capabilities"])
    assert closed >= {
        "CI_DISPATCH",
        "IV_REQUEST",
        "HANDOFF_DELIVER",
        "STEAL_EXECUTE",
        "MERGE",
        "WORKTREE_OPEN",
    }
