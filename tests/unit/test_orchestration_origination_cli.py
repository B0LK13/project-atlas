"""D-PHASE2A-3: ``orchestration.origination.cli.run_origination_scan()``.

Mirrors ``test_orchestration_autonomy_rehydration.py``'s real-git-repo
fixture pattern (a real, self-contained repo with a faked
``origin/main`` remote-tracking ref, no network access required) and
``test_orchestration_origination.py``'s roadmap-writing fixture pattern
-- this module is the one place both are needed together, since
``run_origination_scan()`` is the first origination entry point that
also consults live git inventory for ``base_pin``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    ExecutionHostClass,
    NodeState,
    OwnerGateKind,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.orchestration.origination.cli import EXIT_ERROR, EXIT_OK, run_origination_scan
from project_atlas.orchestration.origination.projection import load_projection


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "init")
    sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", sha)
    return repo


def _anchor(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main="a" * 40,
            predecessor_tree="b" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORIGIN-001-TEST",
            source_directive="D-PHASE2A-3-TEST-FIXTURE",
            source_pr=1,
            merge_commit=main,
            merge_parent_1="a" * 40,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/d-phase2a-3.json",
            evidence_digest="cd" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _write_roadmap(root: Path, items: list[dict[str, object]]) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    fence = json.dumps({"roadmap_items": items}, indent=2)
    (root / "docs" / "ROADMAP.md").write_text(
        f"## Roadmap record\n```json\n{fence}\n```\n", encoding="utf-8"
    )


def _write_skipped_test(root: Path, rel_path: str) -> None:
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(
        'import pytest\n\npytestmark = pytest.mark.skip(reason="not yet implemented")\n\n'
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )


def _write_plain_file(root: Path, rel_path: str, content: str = "# doc\n") -> None:
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _eligible_repo(tmp_path: Path) -> Path:
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: do the thing.\n")
    _write_skipped_test(repo, "tests/test_feature_x.py")
    _write_roadmap(
        repo,
        [
            {
                "id": "feature-x",
                "title": "Feature X",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": ["docs/REQUIREMENTS.md", "tests/test_feature_x.py"],
            }
        ],
    )
    return repo


def test_scan_materializes_a_ready_o1_proposal(tmp_path: Path) -> None:
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_OK
    assert payload["eligible_count"] == 1
    assert payload["materialized_count"] == 1
    assert payload["not_materialized_count"] == 0
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    materialized = payload["materialized"]
    assert isinstance(materialized, list)
    entry = materialized[0]
    assert entry["execution_ready"] is True
    assert entry["reason"] == "READY"
    assert entry["risk_class"] == "O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION"
    assert entry["owner_gate"] is None

    # Durably persisted -- a later reader can find the exact node this
    # scan materialized, not just the in-memory payload.
    projection = load_projection(store)
    assert len(projection.records) == 1
    record = projection.records[0]
    assert record.state == "MATERIALIZED"
    assert record.work_node is not None
    assert record.work_node["package_id"] == entry["work_id"]
    assert record.work_node["execution_host_class"] == ExecutionHostClass.IN_PROCESS.value
    assert record.work_node["state"] == NodeState.DISCOVERED.value


def test_scan_with_no_eligible_work_is_a_clean_empty_result(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_OK
    assert payload["eligible_count"] == 0
    assert payload["materialized_count"] == 0
    assert payload["not_materialized_count"] == 0
    assert payload["materialized"] == []
    assert payload["not_materialized"] == []


def test_scan_never_raises_for_a_malformed_acceptance_contract(tmp_path: Path) -> None:
    """IV finding (PR #663 review, P1): run_origination_scan()'s own
    documented "never raises" contract did not catch
    AcceptanceContractConfigError -- a malformed contract escaped as an
    uncaught exception instead of the function's own fail-closed
    payload, exactly like every other configuration failure it already
    handles."""
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/backlog.md", "- [ ] AAA-001 Real outstanding work\n")
    _write_plain_file(
        repo,
        "docs/acceptance-contracts.yaml",
        "contracts:\n"
        "  - item_id: AAA-001\n"
        "    source_path: docs/backlog.md\n"
        "    evidence: [docs/backlog.md]\n"
        "    proposed_scope: [src/thing.py]\n"
        "    success_criteria: []\n",  # empty -- schema-invalid
    )
    _write_plain_file(
        repo,
        ".atlas-project.yaml",
        "schema_version: 1\n"
        "project:\n"
        "  id: demo-project\n"
        "origination_sources:\n"
        "  - path: docs/backlog.md\n"
        "    format: markdown-task-list\n"
        "origination_acceptance_contracts: docs/acceptance-contracts.yaml\n",
    )
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_ERROR
    assert payload["blocker"] == "ACCEPTANCE_CONTRACT_CONFIG_INVALID"
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False


def test_second_scan_does_not_re_materialize_already_terminal_work(tmp_path: Path) -> None:
    """The correct successor-scan semantic (`originate_new_only`, not
    `originate_all`): once a package's origination_identity is durably
    TERMINAL, a later scan must not re-propose or re-materialize it --
    matching NO_DUPLICATE_ORIGINATION / RESTART_REPLAY."""
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"
    anchor = _anchor(main, tree)

    first, _ = run_origination_scan(
        root=repo, project_id="demo-project", origination_store=store, explicit_trusted=anchor
    )
    assert first["materialized_count"] == 1
    identity = cast("list[dict[str, object]]", first["materialized"])[0]["work_id"]

    from project_atlas.orchestration.origination.projection import mark_terminal

    projection = load_projection(store)
    record = projection.records[0]
    mark_terminal(store, record.origination_identity, node_state="CLOSED")

    second, exit_code = run_origination_scan(
        root=repo, project_id="demo-project", origination_store=store, explicit_trusted=anchor
    )
    assert exit_code == EXIT_OK
    assert second["eligible_count"] == 0
    assert second["materialized_count"] == 0
    # Durable record is untouched, not duplicated.
    assert len(load_projection(store).records) == 1
    del identity  # only needed to document what was closed


def test_scan_fails_closed_on_unsafe_project_id(tmp_path: Path) -> None:
    """Independent-IV finding (PR #647 round 1): an unsafe project_id
    (arbitrary characters, never validated in cli.py itself) used to
    escape run_origination_scan() as an uncaught pydantic.ValidationError
    from deep inside originate_new_only() -> SourceFact construction --
    breaking the function's own "never raises" contract. Must now be
    rejected at the top, before any downstream call, as a clean
    fail-closed payload."""
    repo = _make_repo(tmp_path)
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="bad project id!",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(
            _run_git(repo, "rev-parse", "origin/main"),
            _run_git(repo, "rev-parse", "origin/main^{tree}"),
        ),
    )
    assert exit_code == EXIT_ERROR
    assert payload["blocker"] == "INVALID_PROJECT_ID"
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    # The scan never ran at all -- no store, no partial state.
    assert not (tmp_path / "origination-store").exists()


def test_scan_fails_closed_on_malformed_origination_source_config(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P2): a project's own
    malformed ``origination_sources`` declaration used to escape
    ``run_origination_scan()`` as an uncaught ``OriginationSourceConfigError``
    -- breaking the function's documented "never raises" contract. Must
    come back as a clean fail-closed payload instead."""
    repo = _make_repo(tmp_path)
    (repo / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fixture-proj\norigination_sources: not-a-list\n",
        encoding="utf-8",
    )
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="fixture-proj",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(
            _run_git(repo, "rev-parse", "origin/main"),
            _run_git(repo, "rev-parse", "origin/main^{tree}"),
        ),
    )
    assert exit_code == EXIT_ERROR
    assert payload["blocker"] == "ORIGINATION_SOURCE_CONFIG_INVALID"
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False


def test_scan_fails_closed_on_cross_source_duplicate_item_id(tmp_path: Path) -> None:
    """PR-A review finding (chatgpt-codex-connector, P2): the same stable
    item_id declared authoritative by two different origination sources
    used to escape as an uncaught ``DuplicateItemIdError``. Must come
    back as a clean fail-closed payload instead."""
    repo = _make_repo(tmp_path)
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "a.md").write_text("- [ ] AAA-001 From a\n", encoding="utf-8")
    (repo / "docs" / "b.md").write_text("- [ ] AAA-001 From b\n", encoding="utf-8")
    (repo / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fixture-proj\n"
        "origination_sources:\n"
        "  - path: docs/a.md\n    format: markdown-task-list\n"
        "  - path: docs/b.md\n    format: markdown-task-list\n",
        encoding="utf-8",
    )
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="fixture-proj",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(
            _run_git(repo, "rev-parse", "origin/main"),
            _run_git(repo, "rev-parse", "origin/main^{tree}"),
        ),
    )
    assert exit_code == EXIT_ERROR
    assert payload["blocker"] == "ORIGINATION_DUPLICATE_ITEM_ID"
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False


def test_scan_fails_closed_on_project_id_that_would_overflow_surface_id(
    tmp_path: Path,
) -> None:
    """Independent-IV finding (PR #647 round 1): a project_id that is
    individually valid (safe characters, <=128 chars, same bound
    SourceFact.project_id itself allows) can still combine with the
    fixed-length "-{work_id}" suffix this module appends to overflow
    MutationSurface.surface_id's own 128-char cap -- raising a raw
    ValidationError from inside materialize_work_node(), not a
    MaterializationError, so it used to escape the existing
    `except MaterializationError` entirely. 107 chars is one past this
    module's own 106-char bound (128 - 1 separator - 21-char work_id)."""
    repo = _eligible_repo(tmp_path)
    long_project_id = "p" * 107
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id=long_project_id,
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(
            _run_git(repo, "rev-parse", "origin/main"),
            _run_git(repo, "rev-parse", "origin/main^{tree}"),
        ),
    )
    assert exit_code == EXIT_ERROR
    assert payload["blocker"] == "INVALID_PROJECT_ID"
    assert not (tmp_path / "origination-store").exists()


def test_scan_fails_closed_on_trust_error(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        trust_store=tmp_path / "does-not-exist",
        origination_store=tmp_path / "origination-store",
    )
    assert exit_code == EXIT_ERROR
    assert payload["merge_authorized"] is False
    assert payload["execution_authorized"] is False
    assert "blocker" in payload
    # No projection store was ever created -- the scan never ran.
    assert not (tmp_path / "origination-store").exists()


def test_owner_held_proposal_is_still_materialized_but_owner_gated(tmp_path: Path) -> None:
    """materialize_work_node()'s own contract: OWNER_HELD risk-classified
    proposals are still materialized (not silently dropped), just routed
    to an owner_gate rather than reported execution_ready. The scan must
    surface this distinction, not collapse it into "not materialized".

    proposed_scope is derived from the roadmap item's own `evidence`
    paths (pipeline.py's `_proposed_scope`), not a separate declared
    field -- so an evidence path that itself touches a disqualifying
    fragment (risk.py's `_DISQUALIFYING_PATH_FRAGMENTS`, "migrations/"
    here) is what forces OWNER_HELD, mirrored here rather than
    duplicating risk.py's own list.
    """
    repo = _make_repo(tmp_path)
    _write_plain_file(repo, "docs/REQUIREMENTS.md", "# Requirements\nFR-1: do the risky thing.\n")
    _write_plain_file(repo, "migrations/001_init.sql", "-- migration\n")
    _write_skipped_test(repo, "tests/test_risky.py")
    _write_roadmap(
        repo,
        [
            {
                "id": "risky-item",
                "title": "Risky Item",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": [
                    "docs/REQUIREMENTS.md",
                    "migrations/001_init.sql",
                    "tests/test_risky.py",
                ],
            }
        ],
    )
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=tmp_path / "origination-store",
        explicit_trusted=_anchor(main, tree),
    )
    assert exit_code == EXIT_OK
    # The two buckets combined must equal the eligible count -- whichever
    # bucket it lands in, it must be reported somewhere, not silently
    # vanish.
    total = cast(int, payload["materialized_count"]) + cast(int, payload["not_materialized_count"])
    assert total == payload["eligible_count"] == 1
    # Independent-IV note (PR #647 round 1): asserting the specific
    # outcome directly, not defensively branching on which bucket it
    # landed in -- materialize_work_node()'s own documented contract is
    # that OWNER_HELD nodes ARE materialized, just gated, so this is the
    # one real, non-dead-code outcome for this fixture.
    assert payload["materialized_count"] == 1
    assert payload["not_materialized_count"] == 0
    entry = cast("list[dict[str, object]]", payload["materialized"])[0]
    assert entry["execution_ready"] is False
    assert entry["owner_gate"] in {kind.value for kind in OwnerGateKind}


def test_second_scan_of_still_in_progress_work_does_not_clobber_durable_node(
    tmp_path: Path,
) -> None:
    """D-PHASE2A-2 finding: `originate_new_only()` only excludes TERMINAL
    identities (by design -- see its own docstring), so a second scan
    against the SAME still-non-terminal evidence is a normal, expected
    occurrence once a live governed loop is actually discovering/leasing
    from this projection repeatedly, not an error case. The scan must
    NOT rebuild and overwrite the durable `work_node` in that situation:
    `rehydration.py`'s `find_materialized_work_node()` is the exact
    function a crashed-and-restarted process uses to reconstruct an
    ALREADY-LEASED node from this same durable record -- if a second
    scan clobbered it with a freshly-rebuilt WorkNode (state=DISCOVERED,
    a different base_pin if main moved since), that reconstruction would
    silently diverge from the real governed state the first process's
    lease was actually granted against.

    Proven concretely: advance the repo's `origin/main` between the two
    scans (so a rebuilt WorkNode would carry a different `base_pin` if
    the bug were still present), and assert the durable `work_node` is
    byte-identical after the second scan.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    first, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )
    assert first["materialized_count"] == 1
    first_entry = cast("list[dict[str, object]]", first["materialized"])[0]
    projection_after_first = load_projection(store)
    work_node_after_first = projection_after_first.records[0].work_node
    assert work_node_after_first is not None
    assert work_node_after_first["base_pin"] == main
    assert work_node_after_first["state"] == NodeState.DISCOVERED.value

    # Advance origin/main -- a rebuilt WorkNode would now carry a
    # DIFFERENT base_pin than the durably-recorded one, if the bug were
    # still present.
    _write_plain_file(repo, "docs/UNRELATED.md", "unrelated change\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "advance main")
    new_sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", new_sha)
    assert new_sha != main

    new_main = _run_git(repo, "rev-parse", "origin/main")
    new_tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    second, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(new_main, new_tree),
    )

    assert exit_code == EXIT_OK
    assert second["eligible_count"] == 1  # not TERMINAL yet -- still "eligible"
    assert second["materialized_count"] == 1
    second_entry = cast("list[dict[str, object]]", second["materialized"])[0]
    assert second_entry["work_id"] == first_entry["work_id"]

    # The durable record itself is untouched: still exactly one record,
    # same base_pin as the FIRST scan (never rebuilt against the new
    # main), still DISCOVERED (never silently reset from whatever a real
    # governor would have advanced it to). This is the actual bug this
    # test exists to catch -- checked before the `already_materialized`
    # flag below so the failure surfaces as a real clobbered-base_pin
    # mismatch, not an incidental missing-key error on old code that
    # never had that flag at all.
    projection_after_second = load_projection(store)
    assert len(projection_after_second.records) == 1
    work_node_after_second = projection_after_second.records[0].work_node
    assert work_node_after_second == work_node_after_first
    assert work_node_after_second is not None
    assert work_node_after_second["base_pin"] == main
    assert work_node_after_second["base_pin"] != new_main

    assert second_entry["already_materialized"] is True
    assert first_entry["already_materialized"] is False


def test_content_revision_while_prior_work_in_flight_does_not_create_a_second_live_node(
    tmp_path: Path,
) -> None:
    """D-PHASE2A-2 independent-IV finding (round 2): `origination_identity`
    hashes the item's content digest (`identity.py`) and therefore changes
    when a roadmap item's own content is revised, but `package_id`
    (`work_id_for()`) hashes only `project_id + item_id` and stays
    IDENTICAL across such a revision. Revising the SAME item's title
    between two scans -- while the first scan's non-TERMINAL record for it
    is still in flight -- must not durably create a second, distinct live
    record sharing that package_id: `sync_terminal_governed_states()`
    matches purely by package_id and could otherwise later mark BOTH
    records TERMINAL once only one was ever actually governed to closure,
    permanently and silently losing the other, never-executed proposal.
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    first, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )
    assert first["materialized_count"] == 1
    first_entry = cast("list[dict[str, object]]", first["materialized"])[0]

    # Revise the SAME item ("id" unchanged -> same package_id) with
    # different content ("title" changed -> different item_digest ->
    # different origination_identity), while the first scan's record for
    # it is still MATERIALIZED (not TERMINAL).
    _write_roadmap(
        repo,
        [
            {
                "id": "feature-x",
                "title": "Feature X (revised)",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": ["docs/REQUIREMENTS.md", "tests/test_feature_x.py"],
            }
        ],
    )
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "revise feature-x")
    new_sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", new_sha)
    new_main = _run_git(repo, "rev-parse", "origin/main")
    new_tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    second, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(new_main, new_tree),
    )
    assert exit_code == EXIT_OK
    # The revision is a genuinely new origination_identity, so it is
    # "eligible" -- but it must be refused materialization, not silently
    # dropped and not materialized as a second live node.
    assert second["eligible_count"] == 1
    assert second["materialized_count"] == 0
    assert second["not_materialized_count"] == 1
    second_entry = cast("list[dict[str, object]]", second["not_materialized"])[0]
    assert second_entry["work_id"] == first_entry["work_id"]
    assert second_entry["materialization_error_code"] == "PACKAGE_ID_ALREADY_ACTIVE"

    # Exactly one non-TERMINAL record for this package_id exists durably --
    # the original one, completely untouched.
    projection = load_projection(store)
    active_for_package = [
        row
        for row in projection.records
        if row.state != "TERMINAL"
        and row.work_node is not None
        and row.work_node.get("package_id") == first_entry["work_id"]
    ]
    assert len(active_for_package) == 1
    assert active_for_package[0].work_node is not None
    assert active_for_package[0].work_node["base_pin"] == main
    # Two durable rows total: the original MATERIALIZED one, plus the
    # revision's own PROPOSED-but-never-materialized one (never silently
    # discarded -- honestly recorded, just not turned into a second live
    # node).
    assert len(projection.records) == 2


def test_revised_item_eventually_materializes_once_prior_revision_reaches_terminal(
    tmp_path: Path,
) -> None:
    """REVISED_REAL_WORK_MUST_NOT_DISAPPEAR: the guard added for the
    package_id/origination_identity split (see the sibling test above)
    SERIALIZES a content revision behind the prior revision's own
    non-TERMINAL record -- it must not permanently discard it. Once the
    prior revision (A) is marked TERMINAL (the real, governed-closure
    outcome `sync_terminal_governed_states()` would drive), a later scan
    for the SAME still-current revision (B) must find no conflict left
    and materialize it normally. Proves the serialization strategy is
    safe end-to-end, not merely "doesn't crash right now".
    """
    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    first, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )
    assert first["materialized_count"] == 1
    first_identity = load_projection(store).records[0].origination_identity

    _write_roadmap(
        repo,
        [
            {
                "id": "feature-x",
                "title": "Feature X (revised)",
                "status": "NOT_STARTED",
                "lifecycle": "READY",
                "evidence": ["docs/REQUIREMENTS.md", "tests/test_feature_x.py"],
            }
        ],
    )
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "revise feature-x")
    new_sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", new_sha)
    new_main = _run_git(repo, "rev-parse", "origin/main")
    new_tree = _run_git(repo, "rev-parse", "origin/main^{tree}")

    # Scan #2, while A is still MATERIALIZED: B is refused, as proven by
    # the sibling test -- reconfirmed briefly here for context.
    second, _ = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(new_main, new_tree),
    )
    assert second["materialized_count"] == 0
    assert second["not_materialized_count"] == 1

    # A's governed work completes for real: mark A TERMINAL -- exactly
    # what sync_terminal_governed_states() does once A's own governed
    # node reaches CLOSED.
    from project_atlas.orchestration.origination.projection import mark_terminal

    mark_terminal(store, first_identity, node_state="CLOSED")

    # Scan #3, now that A is TERMINAL: B must no longer be blocked --
    # the exact same still-current revision now materializes.
    third, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(new_main, new_tree),
    )
    assert exit_code == EXIT_OK
    assert third["materialized_count"] == 1
    assert third["not_materialized_count"] == 0
    third_entry = cast("list[dict[str, object]]", third["materialized"])[0]
    # Same package_id as A (same logical item), but this is B's own
    # materialization -- proven by the new base_pin.
    assert third_entry["work_id"] == cast(
        "list[dict[str, object]]", first["materialized"]
    )[0]["work_id"]

    projection = load_projection(store)
    assert len(projection.records) == 2
    a_record = next(r for r in projection.records if r.origination_identity == first_identity)
    b_record = next(r for r in projection.records if r.origination_identity != first_identity)
    assert a_record.state == "TERMINAL"
    assert a_record.terminal_node_state == "CLOSED"
    assert b_record.state == "MATERIALIZED"
    assert b_record.work_node is not None
    assert b_record.work_node["base_pin"] == new_main
    assert b_record.work_node["base_pin"] != main


def test_persist_materialized_if_no_active_conflict_closes_the_toctou_race(
    tmp_path: Path,
) -> None:
    """D-PHASE2A-2 delta-IV finding: the original guard was a two-step
    sequence -- an UNLOCKED `find_active_record_by_package_id()` check,
    followed by a SEPARATE `persist_materialized()` call under its own
    lock. That left a TOCTOU window open: two concurrent callers could
    both observe "no conflict" before either wrote, producing two live
    records sharing one `package_id`. `persist_materialized_if_no_
    active_conflict()` closes this by performing the check and the
    write inside ONE `ProjectIdentityLock` critical section.

    Proven here with two REAL threads racing to materialize two
    different `origination_identity` proposals that share one
    `package_id`, synchronized with a `Barrier` to maximize actual
    contention on the lock -- not merely two sequential calls, which a
    lock would trivially serialize regardless of whether the
    check-then-write sequence inside it was itself atomic.
    """
    import threading

    from project_atlas.orchestration.origination.materialize import materialize_work_node
    from project_atlas.orchestration.origination.pipeline import originate_all
    from project_atlas.orchestration.origination.projection import (
        persist_materialized_if_no_active_conflict,
        persist_proposed,
    )
    from project_atlas.orchestration.origination.risk import classify as classify_risk

    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    assert len(outcomes) == 1
    proposal_a, policy_a = outcomes[0].proposal, outcomes[0].policy
    # A second, DIFFERENT origination_identity claiming the SAME
    # package_id (work_id) -- simulating a content revision, the exact
    # scenario the sibling tests above exercise through a real scan
    # sequence, constructed directly here so both proposals can be
    # persisted/materialized independently of scan ordering.
    proposal_b = proposal_a.model_copy(update={"origination_identity": "b" * 64})

    persist_proposed(store, proposal_a, policy_a)
    persist_proposed(store, proposal_b, policy_a)

    classification = classify_risk(
        proposed_scope=proposal_a.proposed_scope, success_criteria=proposal_a.success_criteria
    )
    node_a = materialize_work_node(
        proposal_a, classification, base_pin=main, surface_id=f"{proposal_a.project_id}-a"
    )
    node_b = materialize_work_node(
        proposal_b, classification, base_pin=main, surface_id=f"{proposal_b.project_id}-b"
    )
    assert node_a.package_id == node_b.package_id  # the shared package_id this test is about

    results: dict[str, tuple[object, object]] = {}
    barrier = threading.Barrier(2)

    def _race(identity: str, node: object) -> None:
        barrier.wait()
        results[identity] = persist_materialized_if_no_active_conflict(store, identity, node)  # type: ignore[arg-type]

    t1 = threading.Thread(target=_race, args=(proposal_a.origination_identity, node_a))
    t2 = threading.Thread(target=_race, args=(proposal_b.origination_identity, node_b))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert not t1.is_alive()
    assert not t2.is_alive()

    result_a = results[proposal_a.origination_identity]
    result_b = results[proposal_b.origination_identity]
    # Exactly one of the two succeeded (a non-None materialized record);
    # the other was correctly refused as a conflict -- never both, and
    # never neither.
    successes = [r for r in (result_a, result_b) if r[0] is not None]
    conflicts = [r for r in (result_a, result_b) if r[1] is not None]
    assert len(successes) == 1
    assert len(conflicts) == 1

    projection = load_projection(store)
    active_for_package = [
        row
        for row in projection.records
        if row.state != "TERMINAL"
        and row.work_node is not None
        and row.work_node.get("package_id") == node_a.package_id
    ]
    assert len(active_for_package) == 1


def test_persist_materialized_if_no_active_conflict_does_not_clobber_same_identity(
    tmp_path: Path,
) -> None:
    """Same-identity persist must not overwrite an already-MATERIALIZED
    work_node. The different-identity TOCTOU test above does not pin
    this: persist_materialized_if_no_active_conflict() only treated a
    *different* origination_identity as a package-id conflict, then
    unconditionally wrote work_node + state. A second call for the
    same identity -- including a concurrent scan that missed the CLI
    skip from a stale snapshot -- would replace the durable node
    find_materialized_work_node() uses to reconstruct a leased node.
    """
    from project_atlas.orchestration.origination.materialize import materialize_work_node
    from project_atlas.orchestration.origination.pipeline import originate_all
    from project_atlas.orchestration.origination.projection import (
        persist_materialized_if_no_active_conflict,
        persist_proposed,
    )
    from project_atlas.orchestration.origination.risk import classify as classify_risk

    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    assert len(outcomes) == 1
    proposal, policy = outcomes[0].proposal, outcomes[0].policy
    persist_proposed(store, proposal, policy)

    classification = classify_risk(
        proposed_scope=proposal.proposed_scope, success_criteria=proposal.success_criteria
    )
    first_node = materialize_work_node(
        proposal, classification, base_pin=main, surface_id=f"{proposal.project_id}-first"
    )
    other_pin = "b" * 40
    assert other_pin != main
    second_node = materialize_work_node(
        proposal, classification, base_pin=other_pin, surface_id=f"{proposal.project_id}-second"
    )

    first_record, first_conflict = persist_materialized_if_no_active_conflict(
        store, proposal.origination_identity, first_node
    )
    assert first_conflict is None
    assert first_record is not None
    assert first_record.work_node is not None
    assert first_record.work_node["base_pin"] == main

    second_record, second_conflict = persist_materialized_if_no_active_conflict(
        store, proposal.origination_identity, second_node
    )
    assert second_conflict is None
    assert second_record is not None
    assert second_record.work_node == first_record.work_node
    assert second_record.work_node is not None
    assert second_record.work_node["base_pin"] == main
    assert second_record.work_node["base_pin"] != other_pin

    projection = load_projection(store)
    assert len(projection.records) == 1
    assert projection.records[0].work_node == first_record.work_node
    assert projection.records[0].state == "MATERIALIZED"


def test_scan_reports_truthful_already_materialized_on_toctou_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cursor Bugbot finding on PR #654 (Low): ``run_origination_scan()``'s
    unlocked ``existing`` read (from ``persist_proposed()``) can still see
    ``PROPOSED`` for an identity a concurrent scan materializes an instant
    later. ``persist_materialized_if_no_active_conflict()`` correctly
    refuses to clobber that durable row (proven above), but this call
    unconditionally reported ``already_materialized: False`` using the
    locally-rebuilt node's fields regardless of which node actually won --
    a lie about durable truth whenever this process lost the race.

    Simulates the race by monkeypatching the projection call to return an
    already-durable record for a *different* base_pin than the one this
    process would have built, with no conflict (same identity) -- exactly
    ``persist_materialized_if_no_active_conflict()``'s real idempotent
    return shape when a concurrent writer won first.
    """
    import project_atlas.orchestration.origination.cli as cli_module
    from project_atlas.orchestration.origination.materialize import materialize_work_node
    from project_atlas.orchestration.origination.pipeline import originate_all
    from project_atlas.orchestration.origination.projection import OriginationRecord
    from project_atlas.orchestration.origination.risk import classify as classify_risk

    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal, policy = outcomes[0].proposal, outcomes[0].policy
    classification = classify_risk(
        proposed_scope=proposal.proposed_scope, success_criteria=proposal.success_criteria
    )
    winning_pin = "c" * 40
    assert winning_pin != main
    winning_node = materialize_work_node(
        proposal, classification, base_pin=winning_pin, surface_id=f"{proposal.project_id}-won"
    )
    winning_record = OriginationRecord(
        origination_identity=proposal.origination_identity,
        project_id=proposal.project_id,
        proposal=proposal.model_dump(mode="json"),
        policy_result=policy.model_dump(mode="json"),
        work_node=winning_node.model_dump(mode="json"),
        state="MATERIALIZED",
    )

    def _fake_persist_materialized_if_no_active_conflict(
        _store: Path, _origination_identity: str, _node: object
    ) -> tuple[OriginationRecord | None, OriginationRecord | None]:
        return winning_record, None

    monkeypatch.setattr(
        cli_module,
        "persist_materialized_if_no_active_conflict",
        _fake_persist_materialized_if_no_active_conflict,
    )

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )

    assert exit_code == EXIT_OK
    materialized = payload["materialized"]
    assert isinstance(materialized, list)
    assert len(materialized) == 1
    entry = materialized[0]
    # Truthful: this process lost the race, nothing it built was written.
    assert entry["already_materialized"] is True
    # Reports the durable winner's identity, not the locally-rebuilt loser.
    assert entry["work_id"] == winning_node.package_id


def test_scan_isolates_a_corrupt_durable_record_to_one_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Independent-verification finding (delta round on PR #654): the new
    ``WorkNode.model_validate(materialized_record.work_node)`` call this
    fix added must follow the same per-item isolation the sibling
    already-known-identity branch above it already has (a corrupt durable
    ``work_node`` there is reported as ``DURABLE_RECORD_CORRUPT`` for just
    that ``work_id``, never fatal to the rest of the batch -- the module's
    own docstring contract). An unguarded ``model_validate`` would let a
    ``pydantic.ValidationError`` escape into the function's outer generic
    handler, which fails the ENTIRE scan closed instead of isolating the
    one bad record.
    """
    import project_atlas.orchestration.origination.cli as cli_module
    from project_atlas.orchestration.origination.pipeline import originate_all
    from project_atlas.orchestration.origination.projection import OriginationRecord

    repo = _eligible_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    store = tmp_path / "origination-store"

    outcomes = originate_all(repo, "demo-project")
    proposal, policy = outcomes[0].proposal, outcomes[0].policy
    corrupt_record = OriginationRecord(
        origination_identity=proposal.origination_identity,
        project_id=proposal.project_id,
        proposal=proposal.model_dump(mode="json"),
        policy_result=policy.model_dump(mode="json"),
        work_node={"not": "a valid WorkNode"},
        state="MATERIALIZED",
    )

    def _fake_persist_materialized_if_no_active_conflict(
        _store: Path, _origination_identity: str, _node: object
    ) -> tuple[OriginationRecord | None, OriginationRecord | None]:
        return corrupt_record, None

    monkeypatch.setattr(
        cli_module,
        "persist_materialized_if_no_active_conflict",
        _fake_persist_materialized_if_no_active_conflict,
    )

    payload, exit_code = run_origination_scan(
        root=repo,
        project_id="demo-project",
        origination_store=store,
        explicit_trusted=_anchor(main, tree),
    )

    # Isolated, not fatal: EXIT_OK with the one bad outcome reported under
    # not_materialized, not an escaped exception / EXIT_ERROR for the
    # whole scan.
    assert exit_code == EXIT_OK
    assert payload["materialized_count"] == 0
    not_materialized = payload["not_materialized"]
    assert isinstance(not_materialized, list)
    assert len(not_materialized) == 1
    assert not_materialized[0]["materialization_error_code"] == "DURABLE_RECORD_CORRUPT"
