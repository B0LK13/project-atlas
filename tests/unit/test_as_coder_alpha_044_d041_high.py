"""D-044 / D-041 HIGH correctness remediations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.attention_hygiene import classify_attention
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import (
    ConnectError,
    connect_project,
    project_slug_from_dirname,
    resolve_bound_project_id,
    resolve_bound_vault,
)
from project_atlas.human_loop import apply_review_decision
from project_atlas.project_architecture import _architecture_rank, build_architecture_lens
from project_atlas.project_brief import build_project_brief
from project_atlas.project_decisions import build_decisions_lens
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_health import explain_source_health


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_attention_empty_vault_is_unknown_not_clear(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = classify_attention(vault, "proj")
    assert report["rollup"] == "UNKNOWN"
    assert report["rollup"] != "CLEAR"
    assert report["inspection"]["positively_inspected"] is False


def test_attention_secret_quarantine_not_clear(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "docs/secrets.env",
                    "source_id": "src-1",
                    "likely_project": "proj",
                }
            ]
        },
    )
    _write(
        vault / "generated" / "reports" / "secret-findings.json",
        [{"path": "docs/secrets.env", "source_id": "src-1"}],
    )
    report = classify_attention(vault, "proj")
    assert report["rollup"] != "CLEAR"
    assert any(item["reason_code"] == "SECRET_QUARANTINE" for item in report["items"])


def test_attention_secret_quarantine_scoped_no_cross_project_leak(tmp_path: Path) -> None:
    """D-047 IV: scoped attention must not inherit another project's secrets."""
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "docs/a.md",
                    "source_id": "src-a",
                    "likely_project": "alpha",
                },
                {
                    "path": "docs/b.env",
                    "source_id": "src-b",
                    "likely_project": "beta",
                },
            ]
        },
    )
    _write(
        vault / "generated" / "reports" / "secret-findings.json",
        {"findings": [{"path": "docs/b.env", "source_id": "src-b"}]},
    )
    # Positive inspection artifacts for alpha so leak would show as ACTION_REQUIRED.
    _write(vault / "review" / "conflicts" / "alpha.json", {"entries": []})
    _write(vault / "review" / "pending" / "alpha.json", {"entries": []})
    _write(vault / "state" / "compilation-outcomes" / "alpha.json", {"candidates": []})
    alpha = classify_attention(vault, "alpha")
    beta = classify_attention(vault, "beta")
    assert not any(item["reason_code"] == "SECRET_QUARANTINE" for item in alpha["items"])
    assert alpha["rollup"] == "CLEAR"
    assert any(item["reason_code"] == "SECRET_QUARANTINE" for item in beta["items"])
    assert beta["rollup"] == "ACTION_REQUIRED"


def test_stranger_defaults_ambiguous_bind_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-047 IV: ambiguous project_ids must not silently become vault-wide."""
    root = tmp_path / "multi"
    root.mkdir()
    vault = root / ".atlas-vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    (vault / "projects" / "beta").mkdir(parents=True)
    bind = root / ".atlas" / "connect.json"
    bind.parent.mkdir(parents=True)
    bind.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_root": root.resolve().as_posix(),
                "vault": ".atlas-vault",
                "project_ids": ["alpha", "beta"],
                "project_id": None,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    assert main(["brief", "--json"]) != EXIT_OK


def test_bind_foreign_project_root_rejected(tmp_path: Path) -> None:
    """D-047 IV: stolen/copied bind must not redirect stranger CLI."""
    victim = tmp_path / "victim"
    attacker = tmp_path / "attacker"
    victim.mkdir()
    attacker.mkdir()
    foreign_vault = tmp_path / "foreign-vault"
    foreign_vault.mkdir()
    (attacker / ".atlas").mkdir()
    (attacker / ".atlas" / "connect.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_root": victim.resolve().as_posix(),
                "vault": foreign_vault.resolve().as_posix(),
                "project_id": "victim-proj",
                "project_ids": ["victim-proj"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ConnectError, match="project_root"):
        resolve_bound_vault(attacker)


def test_attention_unreadable_is_incomplete(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "review" / "pending" / "proj.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    report = classify_attention(vault, "proj")
    assert report["rollup"] in {"INCOMPLETE", "INFORMATIONAL"}
    assert report["rollup"] != "CLEAR"


def test_source_health_unreadable_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    report = explain_source_health(vault, "alpha")
    assert report["health_state"] == "UNREADABLE"
    assert report["honesty"]["unreadable_as_healthy"] is False
    assert any(row["reason_code"] == "ARTIFACT_UNREADABLE" for row in report["sources"])


def test_source_health_unknown_project_not_leaked(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "docs/a.md",
                    "source_id": "src-a",
                    "likely_project": "alpha",
                    "exclusion_reason": "configured-exclusion",
                },
                {
                    "path": "docs/orphan.md",
                    "source_id": "src-orphan",
                    "likely_project": "unknown-project",
                    "exclusion_reason": "configured-exclusion",
                },
                {
                    "path": "docs/b.md",
                    "source_id": "src-b",
                    "likely_project": "beta",
                    "exclusion_reason": "configured-exclusion",
                },
            ]
        },
    )
    _write(
        vault / "generated" / "reports" / "secret-findings.json",
        {
            "findings": [
                {"path": "docs/orphan.md", "source_id": "src-orphan"},
                {"path": "docs/a.md", "source_id": "src-a"},
            ]
        },
    )
    alpha = explain_source_health(vault, "alpha")
    beta = explain_source_health(vault, "beta")
    alpha_sources = {row["source"] for row in alpha["sources"]}
    beta_sources = {row["source"] for row in beta["sources"]}
    assert "docs/a.md" in alpha_sources
    assert "docs/orphan.md" not in alpha_sources
    assert "docs/b.md" not in alpha_sources
    assert "docs/b.md" in beta_sources
    assert "docs/orphan.md" not in beta_sources
    assert alpha["honesty"]["unknown_project_leaked"] is False
    assert alpha["unscoped_omitted_count"] >= 1


def test_decision_heading_theatre_regression(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    note = vault / "projects" / "proj" / "decisions.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# Decisions\n\n## Status\n\nAccepted\n\n## Decision\n\nNoise\n\n"
        "## Consequences\n\nNoise\n\n## ADR-044 Prefer authority evidence\n\nAdopted.\n",
        encoding="utf-8",
    )
    adr_src = vault / "sources" / "imported-documents"
    adr_src.mkdir(parents=True)
    (adr_src / "src-adr.md").write_text(
        "# ADR-099 Formal title\n\n## Status\n\nAccepted\n\n## Decision\n\n"
        "Adopt formal titles only.\n\n## Consequences\n\nFollow-on work.\n",
        encoding="utf-8",
    )
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "docs/adr/ADR-099.md",
                    "source_id": "src-adr",
                    "likely_project": "proj",
                }
            ]
        },
    )
    lens = build_decisions_lens(vault, "proj")
    active = [
        item for item in (lens.get("decisions") or []) if item.get("status") == "ACTIVE_GOVERNING"
    ]
    titles = {item["title"] for item in active}
    assert "Status" not in titles
    assert "Decision" not in titles
    assert "Consequences" not in titles
    assert any("ADR-" in title or "Prefer" in title or "Adopt" in title for title in titles)


def test_unicode_project_slug_no_collision() -> None:
    a = project_slug_from_dirname("文档一")
    b = project_slug_from_dirname("文档二")
    assert a != b
    assert a != "project"
    assert b != "project"
    emoji = project_slug_from_dirname("🚀🚀")
    assert emoji.startswith("project-")
    mixed = project_slug_from_dirname("Atlas文档")
    assert "atlas" in mixed.lower() or "文档" in mixed
    assert project_slug_from_dirname("My Cool App") == "my-cool-app"
    assert project_slug_from_dirname("@@@").startswith("project-")


def test_architecture_root_md_is_ranked() -> None:
    assert _architecture_rank("ARCHITECTURE.md") is not None
    assert _architecture_rank("architecture.md") is not None


def test_architecture_coverage_not_present_when_lens_unknown(tmp_path: Path) -> None:
    root = tmp_path / "arch-cov"
    root.mkdir()
    (root / "README.md").write_text("# Arch Cov\n\nPurpose.\n", encoding="utf-8")
    (root / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nNo extractable Core module table.\n", encoding="utf-8"
    )
    vault = Path(connect_project(root)["vault"])
    lens = build_architecture_lens(vault, "arch-cov")
    # First connect write must already reconcile (architecture before overview).
    overview = json.loads(
        (vault / "generated" / "answers" / "ans-overview-arch-cov.json").read_text(
            encoding="utf-8"
        )
    )
    if lens.get("status") == "unknown":
        assert overview.get("coverage", {}).get("architecture") != "present"
    else:
        assert overview.get("coverage", {}).get("architecture") in {
            "present",
            "partial",
            "absent",
        }


def test_brief_pending_matches_unknown_after_decide(tmp_path: Path) -> None:
    root = tmp_path / "pend-loop"
    root.mkdir()
    (root / "README.md").write_text(
        "# Pend Loop\n\nPurpose.\n\n## Stack\n\nPython.\n",
        encoding="utf-8",
    )
    vault = Path(connect_project(root)["vault"])
    pending_path = vault / "review" / "pending" / "pend-loop.json"
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    _write(
        pending_path,
        {
            "entries": [
                {
                    "review_id": "review-d044-1",
                    "category": "pending-claim",
                    "subject_id": "claim-d044-1",
                    "status": "pending",
                    "reason": "needs owner disposition",
                },
                {
                    "review_id": "review-d044-2",
                    "category": "pending-claim",
                    "subject_id": "claim-d044-2",
                    "status": "pending",
                    "reason": "needs owner disposition",
                },
            ]
        },
    )
    # Stale knowledge-status would previously resurrect decided pending counts.
    status = vault / "projects" / "pend-loop" / "knowledge-status.md"
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(
        "| Signal | Count |\n| --- | --- |\n| claims awaiting review | 9 |\n",
        encoding="utf-8",
    )
    before_unknown = build_unknown_lens(vault, "pend-loop")
    before_state = build_state_lens(vault, "pend-loop")
    before_n = int((before_unknown.get("signals") or {}).get("pending_reviews") or 0)
    assert before_n == 2
    assert int((before_state.get("signals") or {}).get("pending_reviews") or 0) == 2
    apply_review_decision(
        vault,
        project_id="pend-loop",
        review_id="review-d044-1",
        decision="accept",
        reason="Owner verified for D-044 consistency",
    )
    unknown = build_unknown_lens(vault, "pend-loop")
    state = build_state_lens(vault, "pend-loop")
    brief = build_project_brief(vault, "pend-loop", refresh=False)
    after_n = int((unknown.get("signals") or {}).get("pending_reviews") or 0)
    assert after_n == 1
    assert int((state.get("signals") or {}).get("pending_reviews") or 0) == 1
    assert f"pending_reviews={after_n}" in str(brief.get("current_state") or "")


def test_stranger_cli_defaults_after_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "stranger"
    root.mkdir()
    (root / "README.md").write_text("# Stranger\n\nPurpose.\n", encoding="utf-8")
    connect_project(root)
    monkeypatch.chdir(root)
    vault = resolve_bound_vault(root)
    project_id = resolve_bound_project_id(root, vault=vault)
    assert project_id
    assert (
        main(["attention", "--json"]) == EXIT_OK
    )
    assert main(["source-health", "--json"]) == EXIT_OK
    assert main(["brief", "--json"]) == EXIT_OK
    with pytest.raises(ConnectError):
        resolve_bound_project_id(tmp_path)  # no bind


def test_live_api_dual_bind_fail_closed(tmp_path: Path) -> None:
    import threading
    import time

    from project_atlas.api_server import ApiServerError, serve_api
    from project_atlas.scaffold import create_scaffold

    v1 = tmp_path / "api-a"
    v2 = tmp_path / "api-b"
    create_scaffold(v1)
    create_scaffold(v2)
    server = serve_api(v1, host="127.0.0.1", port=18766)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    try:
        with pytest.raises(ApiServerError, match="api-bind-"):
            serve_api(v2, host="127.0.0.1", port=18766)
    finally:
        server.shutdown()


def test_positively_inspected_clear(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "review" / "conflicts" / "proj.json", {"entries": []})
    _write(vault / "review" / "pending" / "proj.json", {"entries": []})
    _write(vault / "state" / "compilation-outcomes" / "proj.json", {"candidates": []})
    report = classify_attention(vault, "proj")
    assert report["rollup"] == "CLEAR"
    assert report["inspection"]["positively_inspected"] is True
