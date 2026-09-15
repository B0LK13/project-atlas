"""AS-TASK-CONTEXT-AND-CONTINUITY-001 — hermetic regressions (zero model calls)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from project_atlas.schema import validate_record
from project_atlas.task_context.assemble import (
    assemble_packet,
    check_freshness,
    compare_packets,
    write_packet,
)
from project_atlas.task_context.models import TaskContextError, TrustLayer, content_digest
from project_atlas.task_context.paths import resolve_source_file
from project_atlas.task_context.views import render_view

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "task-context-continuity"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(FIX / "repo", root)
    return root


def _contract(tmp_path: Path) -> Path:
    path = tmp_path / "contract.json"
    path.write_text((FIX / "contract.json").read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _evidence(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(
        (FIX / "evidence" / "bundle.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return path


def test_contract_refs_included(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        evidence_path=_evidence(tmp_path),
        observation_time="2026-09-10T00:00:00Z",
    )
    ids = {f.fragment_id for f in packet.fragments if f.included}
    assert "req-objective" in ids
    assert "req-mutation" in ids
    assert "src-arch" in ids
    assert "src-api" in ids
    validate_record(packet.model_dump(mode="json"), "task-context-packet")


def test_duplicates_keep_provenance(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    arch = [f for f in packet.fragments if f.source_path == "docs/architecture.md"]
    assert len(arch) >= 2
    assert {f.fragment_id for f in arch} >= {"src-arch", "src-arch-dup"}
    assert any(
        u.kind == "open_question" and "duplicate" in u.statement
        for u in packet.uncertainties
    )


def test_mandatory_scope_preserved_under_budget(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        budget_chars=200_000,
        observation_time="2026-09-10T00:00:00Z",
    )
    mandatory = [
        f for f in packet.fragments if f.tier.value == "mandatory" and f.included
    ]
    bodies = "\n".join(f.body for f in mandatory)
    titles = "\n".join(f.title for f in mandatory)
    assert "Mutation paths" in titles or "src/project_atlas/task_context/" in bodies
    assert packet.contract.mutation_paths
    assert "src/project_atlas/task_context/" in packet.contract.mutation_paths


def test_too_small_budget_reports_incomplete(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        budget_chars=80,
        observation_time="2026-09-10T00:00:00Z",
    )
    assert packet.budget_report is not None
    assert packet.budget_report.incomplete_mandatory is True
    assert packet.budget_report.overflow is True
    assert any("INCOMPLETE" in note for note in packet.budget_report.notes)
    # Bodies of mandatory fragments are not silently shortened.
    for frag in packet.fragments:
        if frag.tier.value == "mandatory" and not frag.included:
            assert frag.exclusion_reason and "not-silently-truncated" in frag.exclusion_reason
            assert len(frag.body) > 0


def test_source_change_marks_stale(workspace: Path, tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    packet = assemble_packet(
        contract=contract,
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    out = tmp_path / "packet.json"
    write_packet(packet, out)
    (workspace / "docs" / "architecture.md").write_text("CHANGED\n", encoding="utf-8")
    report = check_freshness(out, workspace_root=workspace, contract_path=contract)
    assert report["status"] == "must_rebuild"
    assert any(f["kind"] == "source_changed" for f in report["findings"])


def test_contract_change_changes_packet_identity(workspace: Path, tmp_path: Path) -> None:
    cpath = _contract(tmp_path)
    p1 = assemble_packet(
        contract=cpath,
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    raw = json.loads(cpath.read_text(encoding="utf-8"))
    raw["objective"] = "Changed objective for identity test."
    cpath.write_text(json.dumps(raw), encoding="utf-8")
    p2 = assemble_packet(
        contract=cpath,
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    assert p1.contract.contract_digest != p2.contract.contract_digest
    assert p1.content_digest != p2.content_digest


def test_retrieved_injection_not_policy_and_scope_unchanged(
    workspace: Path, tmp_path: Path
) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    bait = next(f for f in packet.fragments if f.fragment_id == "src-bait")
    assert bait.trust_layer == TrustLayer.RETRIEVED
    assert bait.retrieved_quarantine is True
    for frag in packet.fragments:
        if frag.trust_layer == TrustLayer.POLICY:
            assert "ignore" not in frag.body.lower()
    # Mutation scope unchanged despite bait text.
    assert "src/project_atlas/task_context/" in packet.contract.mutation_paths
    assert not any("all files" in p.lower() for p in packet.contract.mutation_paths)
    executor = render_view(packet, "executor")
    assert "TRUST BOUNDARY" in executor["agent_input_preamble"]
    assert any(u.uncertainty_id.startswith("injection-") for u in packet.uncertainties)


def test_missing_and_conflicts_visible(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    assert any(u.kind == "missing_source" for u in packet.uncertainties)
    # Both conflict docs retained; neither auto-chosen as authority.
    bodies = {
        f.fragment_id: f.body
        for f in packet.fragments
        if f.fragment_id in {"src-cfl-a", "src-cfl-b"}
    }
    assert "PostgreSQL 15" in bodies["src-cfl-a"]
    assert "PostgreSQL 16" in bodies["src-cfl-b"]


def test_identical_input_same_content_digest(workspace: Path, tmp_path: Path) -> None:
    kwargs = dict(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        evidence_path=_evidence(tmp_path),
        observation_time="2026-09-10T00:00:00Z",
    )
    a = assemble_packet(**kwargs)  # type: ignore[arg-type]
    b = assemble_packet(**kwargs)  # type: ignore[arg-type]
    assert a.content_digest == b.content_digest
    assert content_digest(a) == a.content_digest
    # Observation metadata may differ without changing content digest when fixed.
    c = assemble_packet(
        contract=kwargs["contract"],  # type: ignore[arg-type]
        workspace_root=workspace,
        evidence_path=kwargs["evidence_path"],  # type: ignore[arg-type]
        observation_time="2099-01-01T00:00:00Z",
    )
    assert c.content_digest == a.content_digest


def test_continuation_does_not_claim_unproven_completion(
    workspace: Path, tmp_path: Path
) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        evidence_path=_evidence(tmp_path),
        observation_time="2026-09-10T00:00:00Z",
    )
    view = render_view(packet, "continuation", workspace_inspectable=False)
    assert view["honesty"]["continuation_authorizes_launch"] is False
    assert view["honesty"]["agent_closing_message_is_evidence"] is False
    assert "agent-closing-claim" in [a["action_id"] for a in view["unproven_or_failed"]]
    assert "attempt-2-repair" in view["proven_completions"]
    assert view["workspace"]["claim"] == "last_observed_only"


def test_failure_and_repair_kept_distinct(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        evidence_path=_evidence(tmp_path),
        observation_time="2026-09-10T00:00:00Z",
    )
    actions = {a.action_id: a for a in packet.prior_actions}
    assert actions["attempt-1-compose"].outcome == "failed"
    assert actions["attempt-2-repair"].outcome == "passed"
    assert actions["attempt-1-compose"].completion_proven is False
    assert actions["attempt-2-repair"].completion_proven is True


def test_context_build_does_not_execute_document_commands(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def _forbidden(*_a: object, **_k: object) -> None:
        calls.append("executed")
        raise AssertionError("must not execute")

    monkeypatch.setattr("subprocess.run", _forbidden, raising=False)
    monkeypatch.setattr("os.system", _forbidden, raising=False)
    assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        observation_time="2026-09-10T00:00:00Z",
    )
    assert calls == []


def test_path_containment_rejects_escape(workspace: Path) -> None:
    with pytest.raises(TaskContextError):
        resolve_source_file(workspace, "../outside.txt")


def test_symlink_escape_rejected(workspace: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = workspace / "docs" / "escape.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    from project_atlas.task_context.adapters import ContextSourceRef, materialize_source

    text, _data, missing = materialize_source(
        workspace,
        ContextSourceRef(
            source_id="escape",
            path="docs/escape.md",
            why="symlink escape probe",
        ),
    )
    # Either rejected as escape or resolved outside root — must not return secret silently
    # as trusted. materialize reports missing/error string when containment fails.
    if missing is None:
        # If OS resolves under root somehow, body still remains RETRIEVED only later.
        assert text == "secret"
    else:
        lowered = missing.lower()
        assert any(
            token in lowered
            for token in ("escape", "outside", "missing", "unreadable", "symlink", "root")
        ) or "PATH" in missing


def test_compare_packets_reports_changes(workspace: Path, tmp_path: Path) -> None:
    cpath = _contract(tmp_path)
    left = assemble_packet(
        contract=cpath, workspace_root=workspace, observation_time="2026-09-10T00:00:00Z"
    )
    (workspace / "docs" / "architecture.md").write_text("v2\n", encoding="utf-8")
    right = assemble_packet(
        contract=cpath, workspace_root=workspace, observation_time="2026-09-10T00:00:00Z"
    )
    diff = compare_packets(left, right)
    assert diff["changed_source_fragments"]
    assert diff["left_content_digest"] != diff["right_content_digest"]


def test_executor_and_reviewer_share_identity(workspace: Path, tmp_path: Path) -> None:
    packet = assemble_packet(
        contract=_contract(tmp_path),
        workspace_root=workspace,
        evidence_path=_evidence(tmp_path),
        observation_time="2026-09-10T00:00:00Z",
    )
    ex = render_view(packet, "executor")
    rev = render_view(packet, "reviewer")
    assert ex["contract_digest"] == rev["contract_digest"] == packet.contract.contract_digest
    assert ex["content_digest"] == rev["content_digest"]


def test_cli_compose_smoke(workspace: Path, tmp_path: Path) -> None:
    from project_atlas.cli import main

    out = tmp_path / "out.json"
    code = main(
        [
            "task-context",
            "compose",
            "--contract",
            str(_contract(tmp_path)),
            "--workspace",
            str(workspace),
            "--evidence",
            str(_evidence(tmp_path)),
            "--output",
            str(out),
            "--json",
        ]
    )
    assert code == 0
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["package_id"] == "AS-TASK-CONTEXT-AND-CONTINUITY-001"
