"""AS-CODER-ALPHA-OBSIDIAN-R1-PROJECTION-001 — living-note gap vs current main."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.connect import connect_project
from project_atlas.obsidian_projection import (
    GENERATOR_ID,
    PACKAGE_ID,
    _escape_marker_tokens,
    _render_attention_section,
    _render_source_health_section,
    materialize_obsidian_projection,
    project_note_path,
)


def test_obsidian_includes_attention_source_health_roadmap(tmp_path: Path) -> None:
    root = tmp_path / "obs2"
    root.mkdir()
    (root / "README.md").write_text("# Obsidian parity\n\nPython brain.\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Keep derived notes\nObsidian is not authority.\n",
        encoding="utf-8",
    )
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])
    note = project_note_path(vault, project_id)
    text = note.read_text(encoding="utf-8")
    assert "## Current project position (derived roadmap)" in text
    assert "ROADMAP!=CANONICAL_TRUTH" in text
    assert "## Attention (what requires action)" in text
    assert "ATTENTION LENS != AUTHORITY" in text
    assert "## Source health (failures / exclusions)" in text
    assert "SOURCE HEALTH != AUTHORITY" in text
    assert "attention_is_health_score: false" in text
    assert "roadmap_is_canonical: false" in text
    assert "obsidian_ui_is_authority: false" in text
    assert "<!-- BEGIN HUMAN: notes -->" in text
    assert "next_answers" in report
    assert "## Suggested next work" in text
    assert "lens_is_authority: false" in text


def test_obsidian_r1_preserves_human_and_does_not_invent(tmp_path: Path) -> None:
    root = tmp_path / "obs2-human"
    root.mkdir()
    (root / "README.md").write_text("# Sparse\n\nNo decisions.\n", encoding="utf-8")
    connected = connect_project(root)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    note = project_note_path(vault, project_id)
    humanized = note.read_text(encoding="utf-8").replace(
        "<!-- BEGIN HUMAN: notes -->\n<!-- END HUMAN: notes -->",
        "<!-- BEGIN HUMAN: notes -->\nKeep human edit.\n<!-- END HUMAN: notes -->",
    )
    note.write_text(humanized, encoding="utf-8")
    materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)
    refreshed = note.read_text(encoding="utf-8")
    assert "Keep human edit." in refreshed
    assert "UNKNOWN" in refreshed
    receipt = json.loads(
        (vault / "generated" / "ops" / "obsidian" / "living-projection-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["canonical_writes"] is False
    assert receipt["honesty"]["lens_is_authority"] is False
    assert receipt["honesty"]["obsidian_ui_is_authority"] is False
    assert receipt["honesty"]["canonical_knowledge_remains_atlas"] is True


def test_obsidian_r1_is_project_scoped(tmp_path: Path) -> None:
    root = tmp_path / "obs-scope"
    root.mkdir()
    (root / "README.md").write_text("# Scoped\n\nHarbor only.\n", encoding="utf-8")
    connected = connect_project(root)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    note = project_note_path(vault, project_id).read_text(encoding="utf-8")
    assert f"project_id: {project_id}" in note or f'project_id: "{project_id}"' in note
    assert "portal-app" not in note


# --- PR #412 remediation regression tests -----------------------------------
# One test per finding, proving the specific bug is fixed rather than just
# re-exercising the happy path.


def test_finding1_confirmed_empty_clear_attention_renders_no_items_not_unknown() -> None:
    """Finding 1: rollup=CLEAR with a positively-returned empty care_about list
    is confirmed-clear data — it must not render the contradictory
    ``rollup=CLEAR`` followed by ``- UNKNOWN``."""
    attention = {"rollup": "CLEAR", "care_about": []}
    lines = _render_attention_section(attention)
    assert "rollup=CLEAR" in "\n".join(lines)
    assert "- no attention items" in lines
    assert "- UNKNOWN" not in lines


def test_finding1_unavailable_malformed_attention_still_renders_unknown() -> None:
    """Finding 1 (negative case): a non-list/absent care_about (not positively
    inspected) must still render UNKNOWN, not "no attention items"."""
    attention = {"rollup": "UNKNOWN", "care_about": None}
    lines = _render_attention_section(attention)
    assert "- UNKNOWN" in lines
    assert "- no attention items" not in lines


def test_finding2_noise_only_exclusions_are_not_erased_from_source_health() -> None:
    """Finding 2: when every exclusion is noise-only, actionable is empty but
    source_count/noise_count are nonzero — the renderer must not claim there
    are no exclusions at all."""
    health = {
        "health_state": "CLEAR",
        "actionable": [],
        "noise": [
            {"source": "node_modules/pkg/index.js", "reason_code": "default-excluded-directory"},
        ],
        "source_count": 1,
        "actionable_count": 0,
        "noise_count": 1,
    }
    text = "\n".join(_render_source_health_section(health))
    assert "no failed/excluded sources in scoped report" not in text
    assert "no actionable failures" in text
    assert "1" in text  # noise count surfaced
    assert "node_modules/pkg/index.js" in text


def test_finding2_true_no_exclusions_still_says_no_exclusions() -> None:
    """Finding 2 (negative case): a report with zero exclusions of any kind
    must keep the original, accurate "no exclusions at all" message."""
    health = {
        "health_state": "CLEAR",
        "actionable": [],
        "noise": [],
        "source_count": 0,
        "actionable_count": 0,
        "noise_count": 0,
    }
    text = "\n".join(_render_source_health_section(health))
    assert "no failed/excluded sources in scoped report" in text


def test_finding3_marker_tokens_in_derived_values_are_escaped() -> None:
    """Finding 3: a source-derived value that contains a literal Atlas
    generated-marker token or a balanced BEGIN/END HUMAN pair must be
    escaped, never rendered raw as real projection structure."""
    evil_path = "weird/<!-- atlas:generated:end --><!-- BEGIN HUMAN: x --><!-- END HUMAN: x -->"
    health = {
        "health_state": "ACTION_REQUIRED",
        "actionable": [
            {
                "source": evil_path,
                "status": "FAILED",
                "reason_code": "FAILED",
                "suggested_next_action": "review",
            }
        ],
        "source_count": 1,
        "actionable_count": 1,
        "noise_count": 0,
    }
    text = "\n".join(_render_source_health_section(health))
    assert "<!-- atlas:generated:end -->" not in text
    assert "<!-- BEGIN HUMAN: x -->" not in text
    assert "<!-- END HUMAN: x -->" not in text
    # The escaped form still shows the underlying content for human readers.
    assert "atlas:generated:end" in text
    assert "BEGIN HUMAN: x" in text


def test_finding3_escape_helper_neutralizes_comment_delimiters() -> None:
    escaped = _escape_marker_tokens("<!-- atlas:generated:start --> and <!-- END HUMAN: a -->")
    assert "<!--" not in escaped
    assert "-->" not in escaped
    assert "&lt;!--" in escaped
    assert "--&gt;" in escaped


def test_finding3_end_to_end_projection_survives_marker_token_in_excluded_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Finding 3 end-to-end: a lens value containing marker syntax (e.g. an
    excluded source path — modeled here via a monkeypatched lens result
    since ``<``/``>``/``:`` are illegal in real Windows filenames) must not
    abort projection nor create a bogus preserved HUMAN block on the next
    materialize call."""
    root = tmp_path / "obs-marker-attack"
    root.mkdir()
    (root / "README.md").write_text("# Marker attack fixture\n", encoding="utf-8")
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])

    evil_source = (
        "weird/<!-- atlas:generated:end --><!-- BEGIN HUMAN: fake --> "
        "gotcha <!-- END HUMAN: fake -->"
    )

    def _evil_health(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "health_state": "ACTION_REQUIRED",
            "actionable": [
                {
                    "source": evil_source,
                    "status": "FAILED",
                    "reason_code": "FAILED",
                    "suggested_next_action": "review",
                }
            ],
            "source_count": 1,
            "actionable_count": 1,
            "noise_count": 0,
        }

    monkeypatch.setattr("project_atlas.source_health.explain_source_health", _evil_health)
    # First materialize: must not raise malformed-generated-markers even
    # though the derived value contains a literal generated-end token.
    materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)
    note = project_note_path(vault, project_id)
    text = note.read_text(encoding="utf-8")
    assert text.count("<!-- atlas:generated:end -->") == 1

    # Second materialize: the fake HUMAN block must not have been picked up
    # as a real preserved human region (it must not appear duplicated, and
    # the real notes stub must remain untouched).
    materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)
    refreshed = note.read_text(encoding="utf-8")
    assert refreshed.count("<!-- BEGIN HUMAN: notes -->") == 1
    # The escaped text may still show "BEGIN HUMAN: fake" as inert prose,
    # but never as a real, parseable comment-marker pair.
    assert "<!-- BEGIN HUMAN: fake -->" not in refreshed
    assert "<!-- END HUMAN: fake -->" not in refreshed


def test_finding4_generator_id_matches_module_package_identity() -> None:
    """Finding 4: GENERATOR_ID must agree with this module's own package
    identity (PACKAGE_ID), not an R1-specific value, for downstream
    generator-id traceability/stability."""
    assert GENERATOR_ID == "atlas-coder-alpha-obsidian-001"
    assert PACKAGE_ID == "AS-CODER-ALPHA-OBSIDIAN-001"
    assert "r1" not in GENERATOR_ID


def test_finding5_unexpected_lens_exception_surfaces_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Finding 5: a non-domain exception (a real programmer bug) from a lens
    must propagate out of materialize_obsidian_projection instead of being
    silently degraded to UNKNOWN by a broad ``suppress(Exception)``."""
    root = tmp_path / "obs-bug-surface"
    root.mkdir()
    (root / "README.md").write_text("# Bug surface fixture\n", encoding="utf-8")
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("programmer bug, not a domain error")

    monkeypatch.setattr("project_atlas.attention_hygiene.classify_attention", _boom)
    with pytest.raises(TypeError):
        materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)


def test_finding6_receipt_honesty_matches_markdown_honesty_flags(tmp_path: Path) -> None:
    """Finding 6: the JSON receipt's honesty block must carry the same
    truth-boundary flags as the markdown "Honesty" section."""
    root = tmp_path / "obs-honesty-sync"
    root.mkdir()
    (root / "README.md").write_text("# Honesty sync fixture\n", encoding="utf-8")
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])
    note_text = project_note_path(vault, project_id).read_text(encoding="utf-8")
    receipt = json.loads(
        (vault / "generated" / "ops" / "obsidian" / "living-projection-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert "- roadmap_is_canonical: false" in note_text
    assert "- attention_is_health_score: false" in note_text
    assert receipt["honesty"]["roadmap_is_canonical"] is False
    assert receipt["honesty"]["attention_is_health_score"] is False


def test_finding7_missing_attention_fields_render_unknown_not_none() -> None:
    """Finding 7: missing level/reason_code/why_seeing_this/what_to_do must
    render UNKNOWN, never the literal string "None"."""
    attention = {
        "rollup": "ACTION_REQUIRED",
        "care_about": [{}],  # every field missing
    }
    text = "\n".join(_render_attention_section(attention))
    assert "None" not in text
    assert "[UNKNOWN] UNKNOWN: UNKNOWN → UNKNOWN" in text


def test_finding7_missing_source_health_fields_render_unknown_not_none() -> None:
    """Finding 7 (source-health rows): missing source/status/reason_code/
    suggested_next_action must render UNKNOWN, never "None"."""
    health = {
        "health_state": "ACTION_REQUIRED",
        "actionable": [{}],  # every field missing
        "source_count": 1,
        "actionable_count": 1,
        "noise_count": 0,
    }
    text = "\n".join(_render_source_health_section(health))
    assert "None" not in text
    assert "UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN" in text
