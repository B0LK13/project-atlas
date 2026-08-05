"""AS-CORE-003 public claims, authority, conflict and transaction coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.domain import ClaimLifecycle
from project_atlas.knowledge_compiler import compile_knowledge, render_bundle

pytestmark = pytest.mark.integration
def _snapshot(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: claims-fixture\n", encoding="utf-8"
    )
    (source / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nDeployment: port 8000\n", encoding="utf-8"
    )
    (source / "OPERATIONS.md").write_text(
        "# Operations\n\nDeployment: port 9000\n", encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    return source, manifest, vault


def test_claims_conflicts_authority_and_provenance_are_project_outputs(tmp_path: Path) -> None:
    _source, manifest, vault = _fixture(tmp_path)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    claims = json.loads((vault / "state/claims/claims-fixture.json").read_text())
    conflicts = json.loads((vault / "review/conflicts/claims-fixture.json").read_text())
    status = json.loads(
        (vault / "generated/reports/knowledge-status-claims-fixture.json").read_text()
    )
    assert len(claims["claims"]) == 2
    assert all(item["provenance"] and item["source_hashes"] for item in claims["claims"])
    assert len(conflicts["entries"]) == 1
    assert conflicts["entries"][0]["state"] == "unresolved"
    assert status["unresolved_conflicts"] == 1
    assert (vault / "projects/claims-fixture/claims.md").is_file()
    assert (vault / "projects/claims-fixture/conflicts.md").is_file()
    assert (vault / "projects/claims-fixture/knowledge-status.md").is_file()


def test_invalid_claim_lifecycle_state_fails_without_mutation(tmp_path: Path) -> None:
    _source, manifest, vault = _fixture(tmp_path)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    state_path = vault / "state/claim-lifecycle/claims-fixture.json"
    state_path.write_text('{"schema_version": 999, "claims": []}\n', encoding="utf-8")
    before = _snapshot(vault)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    assert _snapshot(vault) == before


def test_unchanged_claim_replay_has_no_new_receipt_or_writes(tmp_path: Path) -> None:
    _source, manifest, vault = _fixture(tmp_path)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    before = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*")
        if path.is_file()
    }
    receipts_before = sorted((vault / "receipts/claims").glob("*.json"))
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    lifecycle = json.loads(
        (vault / "state/claim-lifecycle/claims-fixture.json").read_text()
    )
    assert {item["lifecycle"] for item in lifecycle["claims"]} == {"contradicted"}
    before = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*")
        if path.is_file()
    }
    receipts_before = sorted((vault / "receipts/claims").glob("*.json"))
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    after = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert sorted((vault / "receipts/claims").glob("*.json")) == receipts_before


def test_complete_lifecycle_paths_are_source_backed_and_historical(tmp_path: Path) -> None:
    entry = {
        "source_id": "source-a",
        "path": "README.md",
        "classification": "project-overview",
        "source": "sources/imported-documents/source-a.md",
        "sha256": "a" * 64,
        "text": "# Overview\nPurpose: governed project",
        "observed_at": "2020-01-01T00:00:00+00:00",
    }
    first = compile_knowledge("lifecycle-project", [entry], tmp_path)
    for relative, content in render_bundle(first, "lifecycle-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    unchanged = compile_knowledge("lifecycle-project", [entry], tmp_path)
    assert unchanged.claims[0].lifecycle is ClaimLifecycle.UNCHANGED
    changed = dict(entry, text="# Overview\nPurpose: changed", sha256="b" * 64)
    updated = compile_knowledge("lifecycle-project", [changed], tmp_path)
    assert updated.claims[0].lifecycle is ClaimLifecycle.UPDATED
    
    old_claim_id = first.claims[0].claim_id
    replacement = dict(
        changed,
        source_id="source-b",
        sha256="c" * 64,
        text=f"# Overview\nSupersedes: {old_claim_id}\nPurpose: replacement",
    )
    superseded = compile_knowledge("lifecycle-project", [replacement], tmp_path)
    records = {item.claim_id: item for item in superseded.lifecycle}
    assert records[old_claim_id].lifecycle is ClaimLifecycle.SUPERSEDED
    assert records[old_claim_id].superseded_by_claim_id == superseded.claims[0].claim_id
    _assert_restored_claim_replay_transitions_to_unchanged(tmp_path)


def _assert_restored_claim_replay_transitions_to_unchanged(tmp_path: Path) -> None:
    entry = {
        "source_id": "source-restored",
        "source_lineage_id": "sline-restored0000000001",
        "path": "docs/README.md",
        "classification": "project-overview",
        "source": "sources/imported-documents/source-restored.md",
        "sha256": "a" * 64,
        "text": "# Overview\nPurpose: restored project",
    }
    first = compile_knowledge("restore-project", [entry], tmp_path)
    for relative, content in render_bundle(first, "restore-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    removed = compile_knowledge("restore-project", [], tmp_path)
    for relative, content in render_bundle(removed, "restore-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    restored = compile_knowledge(
        "restore-project", [dict(entry, path="archive/README.md")], tmp_path
    )
    assert restored.claims[0].lifecycle is ClaimLifecycle.RESTORED
    restored_rendered = render_bundle(restored, "restore-project")
    for relative, content in restored_rendered.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    replay = compile_knowledge(
        "restore-project", [dict(entry, path="archive/README.md")], tmp_path
    )
    assert replay.claims[0].lifecycle is ClaimLifecycle.UNCHANGED
    assert any(
        transition.previous_state is ClaimLifecycle.RESTORED
        and transition.new_state is ClaimLifecycle.UNCHANGED
        for record in replay.lifecycle
        for transition in record.transitions
    )
    replay_rendered = render_bundle(replay, "restore-project")
    replay_again = compile_knowledge(
        "restore-project", [dict(entry, path="archive/README.md")], tmp_path
    )
    assert render_bundle(replay_again, "restore-project") == replay_rendered
    _assert_restored_claim_rename_preserves_identity(tmp_path)


def _assert_restored_claim_rename_preserves_identity(tmp_path: Path) -> None:
    entry = {
        "source_id": "source-move",
        "source_lineage_id": "sline-move0000000000001",
        "path": "docs/README.md",
        "classification": "project-overview",
        "source": "sources/imported-documents/source-move.md",
        "sha256": "a" * 64,
        "text": "# Overview\nPurpose: moved project",
    }
    first = compile_knowledge("move-project", [entry], tmp_path)
    for relative, content in render_bundle(first, "move-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    removed = compile_knowledge("move-project", [], tmp_path)
    for relative, content in render_bundle(removed, "move-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    moved = compile_knowledge(
        "move-project", [dict(entry, path="archive/README.md")], tmp_path
    )
    assert moved.claims[0].claim_id == first.claims[0].claim_id
    assert moved.claims[0].lifecycle is ClaimLifecycle.RESTORED


def test_conflict_stale_restore_and_rejection_paths(tmp_path: Path) -> None:
    base = {
        "source_id": "source-a",
        "path": "README.md",
        "classification": "project-overview",
        "source": "sources/imported-documents/source-a.md",
        "sha256": "a" * 64,
        "text": "# Overview\nDeployment: port 8000",
        "observed_at": "2020-01-01T00:00:00+00:00",
    }
    conflict_text = "# Overview\nDeployment: port 9000"
    conflict = dict(base, source_id="source-b", sha256="b" * 64, text=conflict_text)
    first = compile_knowledge("state-project", [base, conflict], tmp_path)
    assert {claim.lifecycle for claim in first.claims} == {ClaimLifecycle.CONTRADICTED}
    for relative, content in render_bundle(first, "state-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    policy = tmp_path / ".atlas/claim-lifecycle-policy.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text('{"stale_after_days": 30, "reference": "test-policy"}\n')
    stale_seed = compile_knowledge("stale-project", [base], tmp_path)
    for relative, content in render_bundle(stale_seed, "stale-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    stale_result = compile_knowledge("stale-project", [base], tmp_path)
    assert stale_result.claims[0].lifecycle is ClaimLifecycle.STALE
    assert stale_result.lifecycle[0].transitions[-1].reason == "test-policy"
    stale = compile_knowledge("state-project", [base, conflict], tmp_path)
    assert {claim.lifecycle for claim in stale.claims} == {ClaimLifecycle.CONTRADICTED}
    removed = compile_knowledge("state-project", [], tmp_path)
    assert any(item.lifecycle is ClaimLifecycle.REMOVED_SOURCE for item in removed.lifecycle)
    for relative, content in render_bundle(removed, "state-project").items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    restored = compile_knowledge("state-project", [base, conflict], tmp_path)
    assert all(item.lifecycle is ClaimLifecycle.CONTRADICTED for item in restored.claims)
    assert any(
        transition.new_state is ClaimLifecycle.RESTORED
        for record in restored.lifecycle
        for transition in record.transitions
    )

    rejected_state = tmp_path / "state/claim-lifecycle/rejected-project.json"
    rejected_state.parent.mkdir(parents=True, exist_ok=True)
    rejected_entry = dict(base, source_id="bad-source", text="# Overview\nPurpose: rejected")
    rejected_seed = compile_knowledge("rejected-project", [rejected_entry], tmp_path)
    rejected_claim_id = rejected_seed.claims[0].claim_id
    rejected_state.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "rejected-project",
                "claims": [
                    {
                        "schema_version": 1,
                        "claim_id": rejected_claim_id,
                        "project_id": "rejected-project",
                        "lifecycle": "rejected",
                        "content_sha256": "d" * 64,
                        "source_ids": ["bad-source"],
                        "previous_source_ids": [],
                        "observation_count": 1,
                        "transitions": [],
                        "rejection_reason": "invalid provenance",
                    }
                ],
            }
        )
    )
    rejected = compile_knowledge("rejected-project", [rejected_entry], tmp_path)
    assert not rejected.claims
    assert rejected.lifecycle[0].lifecycle is ClaimLifecycle.REJECTED


def test_multi_project_lifecycle_failure_has_zero_mutations_then_retries_once(
    tmp_path: Path,
) -> None:
    _source, manifest, vault = _fixture(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["sources"][0]["likely_project"] = "aaa-first"
    payload["sources"][1]["likely_project"] = "zzz-second"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    bad_state = vault / "state/claim-lifecycle/zzz-second.json"
    bad_state.parent.mkdir(parents=True, exist_ok=True)
    bad_state.write_text('{"schema_version": 999, "claims": []}\n')
    before = _snapshot(vault)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    assert _snapshot(vault) == before
    bad_state.unlink()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    claims = [
        json.loads(path.read_text())["claims"]
        for path in sorted((vault / "state/claims").glob("*.json"))
    ]
    claim_ids = {item["claim_id"] for items in claims for item in items}
    assert sum(len(items) for items in claims) == len(claim_ids)
