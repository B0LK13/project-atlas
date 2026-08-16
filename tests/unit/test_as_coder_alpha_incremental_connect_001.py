"""AS-CODER-ALPHA-INCREMENTAL-CONNECT-001 — no-change reconnect skip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.agent_handoff import export_agent_context
from project_atlas.connect import ConnectError, connect_project
from project_atlas.incremental_connect import (
    classify_active_delta,
    evaluate_incremental_reconnect,
    identity_lock_path,
    inventory_fingerprint,
)
from project_atlas.project_brief import build_project_brief
from project_atlas.project_next import derive_next_lenses
from project_atlas.source_health import explain_source_health
from project_atlas.source_identity import ProjectIdentityLock


def _seed(root: Path, *, body: str = "v1") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(f"# Incremental Fixture\n\n{body}\n", encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep reconnect incremental.\n",
        encoding="utf-8",
    )
    return root


def _incr(report: dict[str, Any]) -> dict[str, Any]:
    payload = report.get("incremental")
    assert isinstance(payload, dict)
    return payload


def _source_ids(vault: Path) -> list[str]:
    path = vault / "sources" / "manifests" / "source-manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources = raw.get("sources") if isinstance(raw, dict) else None
    ids: list[str] = []
    if isinstance(sources, list):
        for row in sources:
            if isinstance(row, dict) and row.get("source_id"):
                ids.append(str(row["source_id"]))
    return ids


def _truth_fingerprint(vault: Path, project_id: str) -> str:
    chunks: list[bytes] = []
    for relative in (
        Path("projects") / project_id / "project.md",
        Path("generated") / "indexes" / "claims.json",
        Path("sources") / "manifests" / "source-manifest.json",
        Path("state") / "sources.json",
    ):
        path = vault / relative
        if path.is_file():
            chunks.append(relative.as_posix().encode("utf-8") + b"\0" + path.read_bytes())
    return str(len(chunks)) + ":" + str(sum(len(item) for item in chunks))


def _count_ingest(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    from project_atlas import connect as connect_mod

    calls = {"n": 0}
    real = connect_mod.ingest

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(connect_mod, "ingest", wrapped)
    return calls


def test_zero_change_reconnect_skips_ingest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed(tmp_path / "zero-change")
    calls = _count_ingest(monkeypatch)
    first = connect_project(project)
    assert first["status"] == "connected"
    assert _incr(first)["disposition"] == "full_compile"
    assert calls["n"] == 2
    first_ingest = calls["n"]
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    before_ids = _source_ids(vault)
    before_truth = _truth_fingerprint(vault, project_id)
    before_changed = json.loads(
        (vault / "generated" / "answers" / f"ans-changed-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )

    second = connect_project(project)
    assert second["status"] == "connected"
    incr = _incr(second)
    assert incr["disposition"] == "no_change_skip"
    assert incr["ingest_invocations"] == 0
    assert incr["content_changed"] == 0
    assert incr["semantic_records_changed"] == 0
    assert incr["physical_writes"] == 0
    assert incr["projections_regenerated"] == 0
    assert incr["files_inspected"] >= 1
    assert incr["honesty"]["incremental_skip_is_authority"] is False
    assert calls["n"] == first_ingest
    assert second["documents_ingested"] == 0
    assert second["projects"] == first["projects"]

    after_ids = _source_ids(vault)
    assert after_ids == before_ids
    assert len(after_ids) == len(set(after_ids))
    assert _truth_fingerprint(vault, project_id) == before_truth
    after_changed = json.loads(
        (vault / "generated" / "answers" / f"ans-changed-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert after_changed == before_changed
    receipt = json.loads(
        (vault / "generated" / "ops" / "incremental-connect-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["package"] == "AS-CODER-ALPHA-INCREMENTAL-CONNECT-001"
    assert "generated_at" not in receipt
    assert "at" not in receipt.get("generated", {})


def test_one_file_modification_full_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed(tmp_path / "one-mod", body="v1")
    calls = _count_ingest(monkeypatch)
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    (project / "README.md").write_text("# Incremental Fixture\n\nv2\n", encoding="utf-8")
    before = calls["n"]
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "full_compile"
    assert incr["content_changed"] >= 1
    assert "README.md" in incr["delta"]["modified"]
    assert calls["n"] == before + 2
    assert second.get("changed_delta", {}).get("modified_count", 0) >= 1
    payload = json.loads(
        (vault / "generated" / "answers" / f"ans-changed-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert "README.md" in payload["delta"]["modified"]


def test_one_file_addition_full_compiles(tmp_path: Path) -> None:
    project = _seed(tmp_path / "one-add")
    first = connect_project(project)
    (project / "EXTRA.md").write_text("# Extra\n\nnew file\n", encoding="utf-8")
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "full_compile"
    assert "EXTRA.md" in incr["delta"]["added"]
    assert second.get("changed_delta", {}).get("added_count", 0) >= 1
    assert first["status"] == "connected"


def test_one_file_removal_full_compiles(tmp_path: Path) -> None:
    project = _seed(tmp_path / "one-rm")
    connect_project(project)
    (project / "docs" / "DECISIONS.md").unlink()
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "full_compile"
    assert any(path.endswith("DECISIONS.md") for path in incr["delta"]["removed"])
    assert second.get("changed_delta", {}).get("removed_count", 0) >= 1


def test_rename_where_lineage_permits(tmp_path: Path) -> None:
    project = _seed(tmp_path / "rename-ok")
    first = connect_project(project)
    vault = Path(first["vault"])
    src = project / "README.md"
    dst = project / "docs" / "INTRO.md"
    dst.write_bytes(src.read_bytes())
    src.unlink()
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "full_compile"
    renamed = incr["delta"]["renamed"]
    assert renamed
    assert renamed[0]["from"] == "README.md"
    assert renamed[0]["to"] == "docs/INTRO.md"
    assert incr["delta"]["lineage_proven"] is True
    state = json.loads((vault / "state" / "sources.json").read_text(encoding="utf-8"))
    change_states = {
        str(row.get("source_change_state"))
        for row in state.get("sources") or []
        if isinstance(row, dict)
    }
    assert "renamed" in change_states or any(
        row.get("renamed_from") for row in state.get("sources") or [] if isinstance(row, dict)
    )


def test_unproven_rename_stays_unknown(tmp_path: Path) -> None:
    project = _seed(tmp_path / "rename-unknown")
    twin = "# Same bytes\n\nshared\n"
    (project / "A.md").write_text(twin, encoding="utf-8")
    (project / "B.md").write_text(twin, encoding="utf-8")
    connect_project(project)
    (project / "A.md").unlink()
    (project / "C.md").write_text(twin, encoding="utf-8")
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "unknown_full_compile"
    assert incr["reason"] == "rename_lineage_unproven"
    assert incr["delta"]["unknown_moves"]
    assert incr["delta"]["lineage_proven"] is False


def test_malformed_source_fail_closed(tmp_path: Path) -> None:
    project = _seed(tmp_path / "bad-marker")
    connect_project(project)
    (project / ".atlas-project.yaml").write_text("project: [\n", encoding="utf-8")
    with pytest.raises(ConnectError, match="INVALID_PROJECT_MARKER"):
        connect_project(project)


def test_interrupted_prior_connect_does_not_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed(tmp_path / "interrupted")
    calls = _count_ingest(monkeypatch)
    first = connect_project(project)
    vault = Path(first["vault"])
    staging = vault / "generated" / "ops" / ".connect-manifest.staging.json"
    staging.write_text("{}\n", encoding="utf-8")
    before = calls["n"]
    dirty = connect_project(project)
    assert _incr(dirty)["disposition"] == "dirty_prior_full_recompile"
    assert _incr(dirty)["reason"] == "staging_manifest_present"
    assert calls["n"] == before + 2
    assert not staging.is_file()

    receipt = vault / "generated" / "ops" / "connect-receipt.json"
    receipt.unlink()
    missing = connect_project(project)
    assert _incr(missing)["disposition"] == "dirty_prior_full_recompile"
    assert _incr(missing)["reason"] == "prior_receipt_absent"

    receipt.write_text("{not-json", encoding="utf-8")
    unreadable = connect_project(project)
    assert _incr(unreadable)["disposition"] == "dirty_prior_full_recompile"
    assert _incr(unreadable)["reason"] == "prior_receipt_unreadable"


def test_concurrent_identity_lock_fail_closed(tmp_path: Path) -> None:
    project = _seed(tmp_path / "locked")
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    lock = ProjectIdentityLock(identity_lock_path(vault, project_id), wait_seconds=0.15)
    lock.acquire()
    try:
        with pytest.raises(ConnectError, match="identity lock"):
            connect_project(project)
    finally:
        lock.release()


def test_windows_path_behavior_no_casefold_lies() -> None:
    digest = "ab" * 32
    prior = {
        "sources": [
            {
                "path": "docs\\README.md",
                "sha256": digest,
                "likely_project": "demo",
                "source_id": "source-a",
            }
        ]
    }
    current_same = {
        "sources": [
            {
                "path": "docs/README.md",
                "sha256": digest,
                "likely_project": "demo",
                "source_id": "source-a",
            }
        ]
    }
    assert classify_active_delta(prior, current_same).unchanged is True
    current_case = {
        "sources": [
            {
                "path": "docs/readme.md",
                "sha256": digest,
                "likely_project": "demo",
                "source_id": "source-b",
            }
        ]
    }
    delta = classify_active_delta(prior, current_case)
    assert delta.unchanged is False
    # Same bytes + unique hash → proven rename, not a case-fold identity collapse.
    assert delta.renamed == (("docs/README.md", "docs/readme.md"),)
    fp_a = inventory_fingerprint(prior)
    fp_b = inventory_fingerprint(current_case)
    assert fp_a["by_path"] != fp_b["by_path"]
    assert "docs/README.md" in fp_a["by_path"]
    assert "docs/readme.md" in fp_b["by_path"]


def test_source_health_after_incremental_run_still_honest(tmp_path: Path) -> None:
    project = _seed(tmp_path / "health")
    (project / ".env").write_text("SECRET=1\n", encoding="utf-8")
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    second = connect_project(project)
    assert _incr(second)["disposition"] == "no_change_skip"
    health = explain_source_health(vault, project_id)
    assert health["package"] == "AS-CODER-ALPHA-SOURCE-HEALTH-001"
    rows = list(health.get("sources") or []) + list(health.get("noise") or [])
    reasons = {str(row.get("reason_code")) for row in rows}
    assert "sensitive-metadata-only" in reasons
    assert health.get("honesty", {}).get("unknown_is_valid") is True


def test_next_brief_handoff_not_falsely_stale(tmp_path: Path) -> None:
    project = _seed(tmp_path / "fresh-lenses")
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    before_next = json.loads(
        (vault / "generated" / "answers" / f"ans-next-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    before_brief = build_project_brief(vault, project_id, refresh=False)
    second = connect_project(project)
    assert _incr(second)["disposition"] == "no_change_skip"
    after_next = json.loads(
        (vault / "generated" / "answers" / f"ans-next-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert after_next == before_next
    derived = derive_next_lenses(vault, project_ids=[project_id])
    assert derived["honesty"]["read_only"] is True
    assert derived["lenses"]
    assert derived["lenses"][0]["project_id"] == project_id
    brief = build_project_brief(vault, project_id, refresh=False)
    assert brief["project_id"] == project_id
    assert brief["purpose"] == before_brief["purpose"]
    assert brief["honesty"]["lens_is_authority"] is False
    context = export_agent_context(vault, project_id, refresh_brief=False)
    assert context["project_id"] == project_id
    assert context.get("purpose") == brief["purpose"]
    packed = json.loads((vault / str(context["json_path"])).read_text(encoding="utf-8"))
    assert packed["brief"]["project_id"] == project_id
    assert packed["honesty"]["lens_is_authority"] is False
    notes = " ".join(str(item) for item in (brief.get("notes") or []))
    assert "stale" not in notes.lower()


def test_cross_project_skip_does_not_leak(tmp_path: Path) -> None:
    shared = tmp_path / "shared-vault"
    alpha = _seed(tmp_path / "alpha-root", body="alpha")
    beta = _seed(tmp_path / "beta-root", body="beta")
    ra = connect_project(alpha, vault=shared)
    rb = connect_project(beta, vault=shared)
    id_a = str(ra["bound_project_id"])
    id_b = str(rb["bound_project_id"])
    assert id_a != id_b
    before_b = (shared / "projects" / id_b / "project.md").read_bytes()
    before_ids = _source_ids(shared)
    reconnect_a = connect_project(alpha, vault=shared)
    # Last-writer manifest belongs to beta, so alpha reconnect is a full compile.
    assert _incr(reconnect_a)["disposition"] in {"full_compile", "dirty_prior_full_recompile"}
    assert (shared / "projects" / id_b / "project.md").read_bytes() == before_b
    after_ids = _source_ids(shared)
    assert set(before_ids).issubset(set(after_ids))
    reconnect_b = connect_project(beta, vault=shared)
    assert _incr(reconnect_b)["disposition"] in {"full_compile", "dirty_prior_full_recompile"}
    skip_b = connect_project(beta, vault=shared)
    assert _incr(skip_b)["disposition"] == "no_change_skip"
    leaked = [
        row
        for row in json.loads(
            (shared / "sources" / "manifests" / "source-manifest.json").read_text(
                encoding="utf-8"
            )
        ).get("sources")
        or []
        if isinstance(row, dict)
        and row.get("likely_project") == id_a
        and "beta" in str(row.get("path") or "")
    ]
    assert leaked == []
    assert len(after_ids) == len(set(after_ids))


_MANIFEST_RELATIVE = Path("generated") / "ops" / "connect-manifest.json"
_STAGING_RELATIVE = Path("generated") / "ops" / ".connect-manifest.staging.json"
_RECEIPT_RELATIVE = Path("generated") / "ops" / "connect-receipt.json"
_REQUIRED_INDEX_FILES = (
    "authority.json",
    "claims.json",
    "concepts.json",
    "conflicts.json",
    "provenance.json",
    "reviews.json",
    "sources.json",
)


def _write_skip_ready_vault(
    tmp_path: Path,
    *,
    agent_events: list[dict[str, str]] | None = None,
    write_indexes: bool = True,
    empty_index_files: bool = False,
) -> tuple[Path, Path, dict[str, Any]]:
    project = tmp_path / "skip-ready"
    vault = tmp_path / "skip-vault"
    project.mkdir(parents=True)
    source_root = str(project.resolve())
    manifest: dict[str, Any] = {
        "source_root": source_root,
        "sources": [
            {
                "path": "README.md",
                "sha256": "ab" * 32,
                "likely_project": "demo",
                "source_id": "source-a",
            }
        ],
        "agent_events": list(agent_events or []),
    }
    receipt = {
        "schema": "atlas.connect.receipt.v1",
        "status": "connected",
        "vault_id": "vault-1",
        "projects": ["demo"],
        "steps": ["ingest", "validate"],
        "project_root": source_root,
        "compile_options": {
            "include_portfolio": False,
            "skip_validate": False,
            "excludes": [],
            "max_file_size": 10 * 1024 * 1024,
        },
    }
    ops = vault / "generated" / "ops"
    ops.mkdir(parents=True)
    (vault / _MANIFEST_RELATIVE).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (vault / _RECEIPT_RELATIVE).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if write_indexes:
        indexes = vault / "generated" / "indexes"
        indexes.mkdir(parents=True)
        for name in _REQUIRED_INDEX_FILES:
            payload = "" if empty_index_files else "{}\n"
            (indexes / name).write_text(payload, encoding="utf-8")
    return vault, project, manifest


def _evaluate(
    vault: Path,
    project: Path,
    current_manifest: dict[str, Any],
) -> Any:
    return evaluate_incremental_reconnect(
        vault=vault,
        project_root=project,
        current_manifest=current_manifest,
        vault_id="vault-1",
        include_portfolio=False,
        skip_validate=False,
        excludes=[],
        max_file_size=10 * 1024 * 1024,
        manifest_relative=_MANIFEST_RELATIVE,
        staging_relative=_STAGING_RELATIVE,
        receipt_relative=_RECEIPT_RELATIVE,
    )


def test_inbox_only_agent_event_change_does_not_skip(tmp_path: Path) -> None:
    vault, project, prior = _write_skip_ready_vault(tmp_path)
    unchanged = _evaluate(vault, project, prior)
    assert unchanged.disposition == "no_change_skip"
    assert unchanged.reason == "active_sources_unchanged"

    added = _evaluate(
        vault,
        project,
        {**prior, "agent_events": [{"event_id": "AE-inbox-1", "component_sha256": "cd" * 32}]},
    )
    assert added.disposition == "full_compile"
    assert added.reason == "agent_events_changed"
    assert added.delta.unchanged is True

    vault_b, project_b, prior_b = _write_skip_ready_vault(
        tmp_path / "event-edit",
        agent_events=[{"event_id": "AE-inbox-1", "component_sha256": "cd" * 32}],
    )
    edited = _evaluate(
        vault_b,
        project_b,
        {**prior_b, "agent_events": [{"event_id": "AE-inbox-1", "component_sha256": "ef" * 32}]},
    )
    assert edited.disposition == "full_compile"
    assert edited.reason == "agent_events_changed"

    dropped = _evaluate(vault_b, project_b, {**prior_b, "agent_events": []})
    assert dropped.disposition == "full_compile"
    assert dropped.reason == "agent_events_changed"


def test_empty_or_stripped_indexes_do_not_skip(tmp_path: Path) -> None:
    empty_dir, project, manifest = _write_skip_ready_vault(
        tmp_path / "empty-dir", write_indexes=False
    )
    (empty_dir / "generated" / "indexes").mkdir(parents=True)
    empty = _evaluate(empty_dir, project, manifest)
    assert empty.disposition == "dirty_prior_full_recompile"
    assert empty.reason == "indexes_absent"

    stripped, project_s, manifest_s = _write_skip_ready_vault(
        tmp_path / "stripped", write_indexes=True, empty_index_files=True
    )
    blank = _evaluate(stripped, project_s, manifest_s)
    assert blank.disposition == "dirty_prior_full_recompile"
    assert blank.reason == "indexes_absent"

    missing_one, project_m, manifest_m = _write_skip_ready_vault(tmp_path / "partial")
    (missing_one / "generated" / "indexes" / "claims.json").unlink()
    partial = _evaluate(missing_one, project_m, manifest_m)
    assert partial.disposition == "dirty_prior_full_recompile"
    assert partial.reason == "indexes_absent"


def test_stripped_indexes_force_reconnect_recompile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed(tmp_path / "stripped-live")
    calls = _count_ingest(monkeypatch)
    first = connect_project(project)
    assert first["status"] == "connected"
    vault = Path(first["vault"])
    indexes = vault / "generated" / "indexes"
    for path in indexes.iterdir():
        if path.is_file():
            path.unlink()
    before = calls["n"]
    second = connect_project(project)
    incr = _incr(second)
    assert incr["disposition"] == "dirty_prior_full_recompile"
    assert incr["reason"] == "indexes_absent"
    assert calls["n"] == before + 2
    assert (indexes / "claims.json").is_file()
