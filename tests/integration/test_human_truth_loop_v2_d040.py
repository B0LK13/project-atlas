"""D-040 — human truth loop v2 (decide → rematerialize → no resurrection)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.connect import connect_project
from project_atlas.human_loop import apply_review_decision, decisions_path
from project_atlas.project_brief import build_project_brief, materialize_project_briefs
from project_atlas.project_unknown import materialize_unknown_lenses

pytestmark = pytest.mark.integration


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Human Truth Loop v2\n\nPurpose: review decide persistence.\n\n## Stack\n\nPython.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Keep reviews human\nHumans decide accept/reject.\n",
        encoding="utf-8",
    )
    return root


def _pending_count(vault: Path, project_id: str) -> int:
    path = vault / "review" / "pending" / f"{project_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sum(
        1
        for entry in payload.get("entries") or []
        if isinstance(entry, dict) and entry.get("status") == "pending"
    )


def _first_pending_review_id(vault: Path, project_id: str) -> str:
    path = vault / "review" / "pending" / f"{project_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload.get("entries") or []:
        if isinstance(entry, dict) and entry.get("status") == "pending":
            return str(entry["review_id"])
    raise AssertionError("expected at least one pending review")


def test_human_decision_survives_unknown_and_brief_rematerialize(tmp_path: Path) -> None:
    project = _seed(tmp_path / "human-truth-v2")
    report = connect_project(project)
    project_id = str(report["bound_project_id"])
    vault = Path(report["vault"])

    before_pending = _pending_count(vault, project_id)
    assert before_pending >= 1

    review_id = _first_pending_review_id(vault, project_id)
    report = apply_review_decision(
        vault,
        project_id=project_id,
        review_id=review_id,
        decision="accept",
        reason="Owner verified claim from DECISIONS.md",
    )
    assert report["status"] == "ok"

    materialize_unknown_lenses(vault, project_ids=[project_id])
    materialize_project_briefs(vault, project_ids=[project_id], refresh=False)

    after_pending = _pending_count(vault, project_id)
    assert after_pending == before_pending - 1

    decisions = json.loads(decisions_path(vault, project_id).read_text(encoding="utf-8"))
    assert any(item.get("review_id") == review_id for item in decisions.get("decisions") or [])

    unknown = json.loads(
        (vault / "generated" / "answers" / f"ans-unknown-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert unknown["signals"]["pending_reviews"] == after_pending

    # Re-run materialization; decided review must not resurrect as pending.
    materialize_unknown_lenses(vault, project_ids=[project_id])
    build_project_brief(vault, project_id, refresh=True)

    pending_payload = json.loads(
        (vault / "review" / "pending" / f"{project_id}.json").read_text(encoding="utf-8")
    )
    decided = next(
        entry
        for entry in pending_payload.get("entries") or []
        if isinstance(entry, dict) and entry.get("review_id") == review_id
    )
    assert decided["status"] == "resolved"
    assert _pending_count(vault, project_id) == after_pending

    unknown_again = json.loads(
        (vault / "generated" / "answers" / f"ans-unknown-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert unknown_again["signals"]["pending_reviews"] == after_pending
