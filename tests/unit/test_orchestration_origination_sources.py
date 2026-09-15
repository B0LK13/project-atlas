"""D-PHASE2A-RETRY (ORIGINATION_SOURCE_PARITY): generic multi-source
origination -- ``sources.py`` and ``tasklist_adapter.py``.

Fixtures are synthetic and self-contained (built under ``tmp_path``) --
never dependent on the external project-atlas checkout. Nothing here
matches on ``project-atlas``, ``INT-013``, or ``docs/backlog.md``
literally; the parser is exercised generically against invented IDs and
paths, exactly as the production code is (its own config declares real
values -- see ``.atlas-project.yaml``, exercised separately by the CLI
smoke test at the bottom of this file).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from project_atlas.orchestration.origination.adapter import EligibleRoadmapItem
from project_atlas.orchestration.origination.pipeline import originate_all, originate_new_only
from project_atlas.orchestration.origination.proposal import RiskClass
from project_atlas.orchestration.origination.sources import (
    DEFAULT_SOURCES,
    DuplicateItemIdError,
    OriginationSourceConfig,
    OriginationSourceConfigError,
    OriginationSourceFormat,
    eligible_work_items,
    load_origination_sources,
)
from project_atlas.orchestration.origination.tasklist_adapter import eligible_task_list_items


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_marker(root: Path, origination_sources_yaml: str | None) -> None:
    body = "schema_version: 1\nproject:\n  id: fixture-proj\n"
    if origination_sources_yaml is not None:
        body += origination_sources_yaml
    _write(root, ".atlas-project.yaml", body)


# ---------------------------------------------------------------------------
# sources.py: explicit-authority config loading (SOURCE_AUTHORITY = EXPLICIT)
# ---------------------------------------------------------------------------


def test_no_marker_falls_back_to_default_source_unchanged(tmp_path: Path) -> None:
    assert load_origination_sources(tmp_path) == DEFAULT_SOURCES
    assert (
        OriginationSourceConfig(
            path="docs/ROADMAP.md", format=OriginationSourceFormat.STRUCTURED_ROADMAP
        ),
    ) == DEFAULT_SOURCES


def test_marker_without_origination_sources_key_falls_back_to_default(tmp_path: Path) -> None:
    _write_marker(tmp_path, None)
    assert load_origination_sources(tmp_path) == DEFAULT_SOURCES


def test_explicit_declaration_is_used(tmp_path: Path) -> None:
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    sources = load_origination_sources(tmp_path)
    assert sources == (
        OriginationSourceConfig(
            path="docs/backlog.md", format=OriginationSourceFormat.MARKDOWN_TASK_LIST
        ),
    )


def test_malformed_origination_sources_fails_closed(tmp_path: Path) -> None:
    _write_marker(tmp_path, "origination_sources: not-a-list\n")
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_unknown_format_fails_closed(tmp_path: Path) -> None:
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/x.md\n    format: freeform-prose\n",
    )
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_traversal_path_rejected(tmp_path: Path) -> None:
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: ../outside.md\n    format: markdown-task-list\n",
    )
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_empty_marker_file_falls_back_to_default(tmp_path: Path) -> None:
    """A marker file that exists but is entirely empty (parses to
    ``None``) is genuinely "no configuration", not malformed."""
    _write(tmp_path, ".atlas-project.yaml", "")
    assert load_origination_sources(tmp_path) == DEFAULT_SOURCES


def test_marker_parses_to_non_mapping_fails_closed(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P2): a marker that
    parses to a scalar/list (templating error, truncated file) must fail
    closed rather than silently resolve to DEFAULT_SOURCES."""
    _write(tmp_path, ".atlas-project.yaml", "- just\n- a\n- list\n")
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_explicit_null_origination_sources_fails_closed(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P2): a *present but
    null* origination_sources key is a declaration that says nothing
    meaningful -- it must not be treated the same as the key being
    genuinely absent."""
    _write_marker(tmp_path, "origination_sources:\n")
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_duplicate_source_declaration_fails_closed(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P2): the same
    (path, format) pair declared twice must be rejected, not silently
    scanned twice (which would inflate eligible_count)."""
    _write_marker(
        tmp_path,
        "origination_sources:\n"
        "  - path: docs/backlog.md\n    format: markdown-task-list\n"
        "  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    with pytest.raises(OriginationSourceConfigError):
        load_origination_sources(tmp_path)


def test_readme_checklist_never_scanned_without_declaration(tmp_path: Path) -> None:
    """A checklist sitting in an undeclared file (README, tutorial, issue
    template shape) must never become authoritative work merely because
    it matches checkbox syntax."""
    _write(
        tmp_path,
        "README.md",
        "# Fixture\n\n- [ ] AAA-001 Set up your dev environment\n",
    )
    # No marker at all -- default source (docs/ROADMAP.md) only.
    assert eligible_work_items(tmp_path) == ()


# ---------------------------------------------------------------------------
# tasklist_adapter.py: generic Markdown task-list parsing
# ---------------------------------------------------------------------------


def test_unchecked_item_with_stable_id_is_eligible(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [ ] ZZZ-001 Do the bounded thing\n")
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 1
    item = items[0]
    assert item.item_id == "ZZZ-001"
    assert item.title == "Do the bounded thing"
    assert item.status == "NOT_STARTED"
    assert item.lifecycle == "READY"
    assert item.source_path == "docs/backlog.md"
    assert item.depends_on == ()
    assert item.evidence == ()
    assert item.blockers == ()


def test_checked_item_is_never_originated(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [x] ZZZ-002 Already done\n")
    assert eligible_task_list_items(tmp_path, "docs/backlog.md") == ()


def test_case_insensitive_checked_marker(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [X] ZZZ-003 Also already done\n")
    assert eligible_task_list_items(tmp_path, "docs/backlog.md") == ()


def test_line_without_stable_id_is_skipped_not_an_error(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] lowercase prose with no id\n"
        "- [ ] Chronicle / Ambient Knowledge runtime (no id here either)\n",
    )
    assert eligible_task_list_items(tmp_path, "docs/backlog.md") == ()


def test_section_context_captured(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "## Epic Alpha\n\n- [ ] AAA-001 First task\n\n## Epic Beta\n\n- [ ] BBB-001 Second task\n",
    )
    items = {item.item_id: item for item in eligible_task_list_items(tmp_path, "docs/backlog.md")}
    assert items["AAA-001"].section_context == "Epic Alpha"
    assert items["BBB-001"].section_context == "Epic Beta"


def test_duplicate_id_within_source_is_flagged_as_blocker(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] DUP-001 First occurrence\n- [ ] DUP-001 Second occurrence\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 2
    for item in items:
        assert any("duplicate task-list item id" in blocker for blocker in item.blockers)


def test_blocker_language_in_title_is_preserved_not_dropped(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] GATE-001 Owner merge gate (not this package)\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 1
    assert items[0].blockers  # item is still reported, not silently dropped
    assert any("blocker language" in b for b in items[0].blockers)


def test_merge_authorization_equals_not_granted_convention_is_recognized(
    tmp_path: Path,
) -> None:
    """IV finding (PR #663 review): this repository's own actual
    docs/backlog.md convention (e.g. D-PHASE2A-2) writes
    `MERGE_AUTHORIZATION = NOT_GRANTED` with an `=` and surrounding
    spaces -- neither of the two pre-existing keyword variants
    (underscore-joined, space-joined) matched that substring."""
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] GATE-002 Some real work. `MERGE_AUTHORIZATION = NOT_GRANTED`.\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 1
    assert items[0].blockers


def test_ordinary_title_has_no_blocker_language(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [ ] PLAIN-001 Fix the thing normally\n")
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert items[0].blockers == ()


def test_overlong_title_is_bounded_but_identity_stays_full_fidelity(tmp_path: Path) -> None:
    long_tail = "x" * 400
    _write(tmp_path, "docs/backlog.md", f"- [ ] LONG-001 {long_tail}\n")
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 1
    assert len(items[0].title) <= 256
    assert items[0].title.endswith("…")

    # Two items differing only *beyond* the truncation point must still be
    # distinct identities -- the digest is computed on the untruncated text.
    _write(
        tmp_path,
        "docs/backlog2.md",
        f"- [ ] LONG-001 {'x' * 399}y\n",
    )
    other = eligible_task_list_items(tmp_path, "docs/backlog2.md")
    assert other[0].item_digest != items[0].item_digest


def test_unrelated_sibling_edit_does_not_change_item_identity(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 Stable task\n- [ ] BBB-001 Other task\n",
    )
    before_items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    before = {i.item_id: i.item_digest for i in before_items}
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 Stable task\n- [ ] BBB-001 A completely different title now\n",
    )
    after_items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    after = {i.item_id: i.item_digest for i in after_items}
    assert before["AAA-001"] == after["AAA-001"]
    assert before["BBB-001"] != after["BBB-001"]


def test_missing_file_yields_empty_tuple_not_error(tmp_path: Path) -> None:
    assert eligible_task_list_items(tmp_path, "docs/does-not-exist.md") == ()


def test_traversal_source_path_yields_empty_tuple(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.md"
    outside.write_text("- [ ] SECRET-001 leak\n", encoding="utf-8")
    assert eligible_task_list_items(tmp_path, "../outside-secret.md") == ()


def test_continuation_lines_join_title_and_are_scanned_for_blockers(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P1): a task's blocker
    language two lines below its checkbox (this repository's own
    docs/backlog.md does exactly this for DOGFOOD-001) must still be
    detected -- not just text on the checkbox's own physical line."""
    _write(
        tmp_path,
        "docs/backlog.md",
        textwrap.dedent(
            """\
            - [ ] GATE-002 Minimal-diff marker append + CLI disclosure of
                  source-tree identity writes, but blocked on an owner
                  decision before it can be materialized without a gate.
            """
        ),
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert len(items) == 1
    item = items[0]
    assert "identity writes" in item.title
    assert item.blockers  # continuation-line blocker language was not dropped


def test_continuation_stops_at_blank_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 First line only\n\nUnrelated paragraph, not a continuation.\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert items[0].title == "First line only"


def test_continuation_stops_at_next_checkbox(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 First item\n- [ ] BBB-001 Second item, not a continuation of AAA-001\n",
    )
    items = {i.item_id: i for i in eligible_task_list_items(tmp_path, "docs/backlog.md")}
    assert items["AAA-001"].title == "First item"
    assert items["BBB-001"].title == "Second item, not a continuation of AAA-001"


def test_continuation_stops_at_heading(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 First item\n## Next section\n- [ ] BBB-001 Second item\n",
    )
    items = {i.item_id: i for i in eligible_task_list_items(tmp_path, "docs/backlog.md")}
    assert items["AAA-001"].title == "First item"
    assert items["BBB-001"].section_context == "Next section"


def test_continuation_does_not_swallow_nested_checkbox(tmp_path: Path) -> None:
    """An indented, nested checkbox line must still be recognized as its
    own item (or at least never silently absorbed as plain continuation
    prose of its parent), even though it is indented like ordinary
    continuation text."""
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 Parent item\n  - [ ] BBB-001 Nested child, not prose\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    parent = next(i for i in items if i.item_id == "AAA-001")
    assert "BBB-001" not in parent.title
    assert "Nested child" not in parent.title


def test_unindented_line_after_checkbox_is_not_a_continuation(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        "- [ ] AAA-001 First item\nThis line starts at column 0, not a continuation.\n",
    )
    items = eligible_task_list_items(tmp_path, "docs/backlog.md")
    assert items[0].title == "First item"


# ---------------------------------------------------------------------------
# eligible_work_items(): cross-source aggregation and identity safety
# ---------------------------------------------------------------------------


def test_generic_scan_finds_only_declared_source(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [ ] AAA-001 Task one\n")
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    items = eligible_work_items(tmp_path)
    assert [i.item_id for i in items] == ["AAA-001"]


def test_cross_source_duplicate_id_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [ ] AAA-001 From backlog\n")
    _write(tmp_path, "docs/second.md", "- [ ] AAA-001 From a second declared source\n")
    _write_marker(
        tmp_path,
        "origination_sources:\n"
        "  - path: docs/backlog.md\n    format: markdown-task-list\n"
        "  - path: docs/second.md\n    format: markdown-task-list\n",
    )
    with pytest.raises(DuplicateItemIdError):
        eligible_work_items(tmp_path)


def test_backward_compatible_roadmap_still_works_unchanged(tmp_path: Path) -> None:
    """A project using only the original docs/ROADMAP.md format, with no
    origination_sources declaration at all, is completely unaffected by
    this generalization."""
    import json

    (tmp_path / "docs").mkdir(parents=True)
    fence = json.dumps(
        {
            "roadmap_items": [
                {
                    "id": "R-001",
                    "title": "Original format item",
                    "status": "not_started",
                    "lifecycle": "ready",
                }
            ]
        },
        indent=2,
    )
    (tmp_path / "docs" / "ROADMAP.md").write_text(
        f"## Roadmap record\n```json\n{fence}\n```\n", encoding="utf-8"
    )
    items = eligible_work_items(tmp_path)
    assert len(items) == 1
    assert items[0].item_id == "R-001"
    assert items[0].source_path == "docs/ROADMAP.md"


# ---------------------------------------------------------------------------
# Full pipeline: originate_all()/originate_new_only() consume the generic
# source model end to end (CHECKED_ITEMS_ORIGINATED, STALE_ITEM_HANDLING,
# SUCCESSOR_DEDUP, CROSS_PROCESS_IDENTITY).
# ---------------------------------------------------------------------------


def test_originate_all_finds_task_list_candidate_and_never_originates_checked(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "docs/backlog.md",
        textwrap.dedent(
            """\
            ## Epic

            - [x] AAA-000 Already implemented (must not appear)
            - [ ] AAA-001 Real outstanding work
            """
        ),
    )
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    outcomes = originate_all(tmp_path, "fixture-proj")
    ids = [o.proposal.title for o in outcomes]
    assert "AAA-000" not in " ".join(ids)  # CHECKED_ITEMS_ORIGINATED = 0
    assert len(outcomes) == 1
    assert outcomes[0].proposal.authoritative_source.location == "docs/backlog.md"


def test_evidence_free_task_list_item_is_owner_held_not_leasable_o1(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P1): a markdown-task-
    list item never carries corroborating evidence (evidence=() always --
    no evidence-citation convention exists in bare checkbox syntax), so
    its proposed_scope is always empty. Before the risk.classify() fix,
    an empty scope had nothing for the disqualifier scan to check and
    classified O1 with owner_gate=None -- exactly the shape a live
    governor could lease despite policy.execution_ready being (correctly)
    False. An ordinary, blocker-free item must now materialize
    OWNER_HELD, matching the policy layer's own INSUFFICIENT_ACCEPTANCE_
    CONTRACT signal instead of contradicting it."""
    _write(tmp_path, "docs/backlog.md", "- [ ] AAA-001 Ordinary unblocked task\n")
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    outcomes = originate_all(tmp_path, "fixture-proj")
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.proposal.risk_class == RiskClass.OWNER_HELD
    assert outcome.policy.execution_ready is False


def test_successor_dedup_and_stale_item_handling(tmp_path: Path) -> None:
    """A completed item whose backlog checkbox was never flipped (a stale
    record) must not be re-proposed once its origination_identity is
    durably TERMINAL -- successor scans see NO_ELIGIBLE_WORK for it, not a
    repeat proposal (SUCCESSOR_DEDUP, STALE_ITEM_HANDLING)."""
    from project_atlas.orchestration.origination.projection import mark_terminal, persist_proposed

    _write(tmp_path, "docs/backlog.md", "- [ ] AAA-001 Stale but still unchecked\n")
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    store = tmp_path / "origination-store"
    first = originate_new_only(tmp_path, "fixture-proj", store)
    assert len(first) == 1
    outcome = first[0]
    persist_proposed(store, outcome.proposal, outcome.policy)
    mark_terminal(store, outcome.proposal.origination_identity, node_state="CERTIFIED")

    # A brand-new call (simulating a fresh process rehydrating durable
    # state) against the SAME, still-unchecked backlog file must not
    # re-propose the now-TERMINAL identity.
    second = originate_new_only(tmp_path, "fixture-proj", store)
    assert second == ()


def test_cross_process_identity_is_stable_across_independent_scans(tmp_path: Path) -> None:
    _write(tmp_path, "docs/backlog.md", "- [ ] AAA-001 Stable across processes\n")
    _write_marker(
        tmp_path,
        "origination_sources:\n  - path: docs/backlog.md\n    format: markdown-task-list\n",
    )
    first = originate_all(tmp_path, "fixture-proj")
    second = originate_all(tmp_path, "fixture-proj")
    assert first[0].proposal.origination_identity == second[0].proposal.origination_identity
    assert first[0].proposal.work_id == second[0].proposal.work_id


def test_eligible_roadmap_item_backward_compatible_default_source_path() -> None:
    """The dataclass's new fields default exactly to the pre-existing
    behavior for any caller (including test fixtures) that still
    constructs it positionally/without the new fields."""
    item = EligibleRoadmapItem(
        item_id="X-1",
        item_digest="a" * 64,
        title="t",
        status="NOT_STARTED",
        lifecycle="READY",
        depends_on=(),
        blockers=(),
        evidence=(),
        roadmap_text="",
        roadmap_digest="b" * 64,
    )
    assert item.source_path == "docs/ROADMAP.md"
    assert item.section_context is None
