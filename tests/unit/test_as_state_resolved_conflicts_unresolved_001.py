"""AS-STATE-RESOLVED-001 — resolved conflicts must not count as unresolved.

Conflict records use ``state: unresolved|resolved``. Current-state and
unknown lenses previously counted every conflict entry (state lens) or
treated missing pending-queue ``status`` as pending (unknown lens), so a
human-resolved row still produced ``unresolved_conflicts>=1``,
``rollup=attention|conflict``, and brief next-work to re-litigate a
closed conflict.

Missing ``state`` still defaults to unresolved (fail-closed). Unreadable
overlay behavior is unchanged (#923/#926).
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.project_brief import build_project_brief
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.web_api.conflicts import list_project_conflicts

_PID = "demo-proj"


def _seed_project(vault: Path, *, lifecycle: str = "active") -> None:
    note = vault / "projects" / _PID / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# demo\n<!-- atlas:generated:start -->\n## Semantic record\n```json\n"
        + json.dumps(
            {
                "project_id": _PID,
                "lifecycle": lifecycle,
                "sources": [],
                "coverage": [],
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )


def _write_conflicts(vault: Path, entries: list[dict[str, object]]) -> None:
    path = vault / "review" / "conflicts" / f"{_PID}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": _PID,
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _resolved_entry() -> dict[str, object]:
    return {
        "conflict_id": "c-resolved",
        "subject": "doc:db",
        "field": "version",
        "claims": [
            {"source_id": "a", "claim": "15"},
            {"source_id": "b", "claim": "16"},
        ],
        "state": "resolved",
        "resolution": "16",
    }


def _unresolved_entry() -> dict[str, object]:
    return {
        "conflict_id": "c-open",
        "subject": "doc:db",
        "field": "engine",
        "claims": [
            {"source_id": "a", "claim": "pg"},
            {"source_id": "b", "claim": "mysql"},
        ],
        "state": "unresolved",
    }


def test_resolved_only_conflict_is_not_unresolved(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [_resolved_entry()])

    state = build_state_lens(vault, _PID)
    unknown = build_unknown_lens(vault, _PID)

    assert state["signals"]["unresolved_conflicts"] == 0
    assert state["rollup"] != "attention"
    assert unknown["signals"]["unresolved_conflicts"] == 0
    assert unknown["rollup"] != "conflict"
    assert "unresolved_conflicts=" not in " ".join(
        str(item) for item in unknown["signals"]["unknown_items"]
    )


def test_mixed_resolved_and_unresolved_counts_only_open(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [_resolved_entry(), _unresolved_entry()])

    state = build_state_lens(vault, _PID)
    unknown = build_unknown_lens(vault, _PID)

    assert state["signals"]["unresolved_conflicts"] == 1
    assert state["rollup"] == "attention"
    assert unknown["signals"]["unresolved_conflicts"] == 1
    assert unknown["rollup"] == "conflict"


def test_missing_state_defaults_to_unresolved(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [{"id": "c1"}, {"id": "c2"}])

    state = build_state_lens(vault, _PID)
    unknown = build_unknown_lens(vault, _PID)

    assert state["signals"]["unresolved_conflicts"] == 2
    assert unknown["signals"]["unresolved_conflicts"] == 2


def test_live_resolved_file_does_not_resurrect_stale_status(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [_resolved_entry()])
    status = vault / "projects" / _PID / "knowledge-status.md"
    status.write_text(
        "# Knowledge status\n\n"
        "| Signal | Count |\n|---|---:|\n"
        "| unresolved conflicts | 2 |\n"
        "| claims awaiting review | 0 |\n"
        "| stale claims | 0 |\n"
        "| sources complete | 1 |\n"
        "| sources failed | 0 |\n",
        encoding="utf-8",
    )

    state = build_state_lens(vault, _PID)
    unknown = build_unknown_lens(vault, _PID)

    assert state["signals"]["unresolved_conflicts"] == 0
    assert unknown["signals"]["unresolved_conflicts"] == 0


def test_brief_does_not_ask_to_resolve_closed_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [_resolved_entry()])

    brief = build_project_brief(vault, _PID, refresh=True)
    next_work = (
        brief.get("suggested_next_work")
        or brief.get("next_work")
        or brief.get("next")
        or []
    )
    if isinstance(next_work, list):
        joined = " ".join(str(item) for item in next_work)
    else:
        joined = str(next_work)
    assert "Resolve unresolved conflicts" not in joined


def test_web_conflicts_projection_skips_resolved_rows(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_project(vault)
    _write_conflicts(vault, [_resolved_entry(), _unresolved_entry()])

    result = list_project_conflicts(vault, _PID)
    assert result["conflict_count"] == 1
    assert [row["conflict_id"] for row in result["conflicts"]] == ["c-open"]
