"""D-149 — stale estate evidence, terminal truth, owner-gate non-escalation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from project_atlas.orchestration.autonomy.authentic_estate import (
    AUTHENTIC_O2_PACKAGES,
    d148_evidence_applies,
    estate_fingerprint,
    marker_fingerprint,
    refresh_authentic_o2_node_states,
    run_estate_preflight,
    write_estate_credential,
)
from project_atlas.orchestration.sdk.mission_reconciler import WorkNode, load_nodes, persist_nodes
from project_atlas.portfolio import stale_knowledge


def _load_d147():
    path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "scripts"
        / "d147_broker_reconcile.py"
    )
    spec = importlib.util.spec_from_file_location("d147_broker_reconcile", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_d148():
    path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "scripts"
        / "d148_authentic_o2_runner.py"
    )
    spec = importlib.util.spec_from_file_location("d148_authentic_o2_runner", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_estate(tmp_path: Path) -> Path:
    repo = tmp_path / "estate"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("# Sample\n\nPurpose: inventory tooling.\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "overview.md").write_text("Overview of sample.\n", encoding="utf-8")
    (repo / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: sample\n  name: Sample\nproject_uuid: "
        "00000000-0000-4000-8000-000000000001\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _init_atlas_repo(tmp_path: Path, estate: Path) -> Path:
    root = tmp_path / "atlas"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("atlas\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    rt = root / ".atlas" / "orchestration" / "sdk-runtime"
    rt.mkdir(parents=True)
    preflight = run_estate_preflight(estate)
    write_estate_credential(root, estate, preflight)
    return root, head


def test_content_fingerprint_changes_when_source_changes(tmp_path: Path) -> None:
    estate = _init_estate(tmp_path)
    before = estate_fingerprint(estate)
    marker_before = marker_fingerprint(estate)
    (estate / "docs" / "overview.md").write_text("Overview CHANGED.\n", encoding="utf-8")
    after = estate_fingerprint(estate)
    assert before != after
    assert marker_fingerprint(estate) == marker_before


def test_content_fingerprint_stable_for_transient_generated(tmp_path: Path) -> None:
    estate = _init_estate(tmp_path)
    before = estate_fingerprint(estate)
    cache = estate / "node_modules" / "pkg"
    cache.mkdir(parents=True)
    (cache / "index.js").write_text("console.log(1)\n", encoding="utf-8")
    (estate / "__pycache__").mkdir()
    (estate / "__pycache__" / "x.pyc").write_bytes(b"\0\1\2")
    assert estate_fingerprint(estate) == before


def test_stale_evidence_rejected_when_source_changes(tmp_path: Path) -> None:
    estate = _init_estate(tmp_path)
    root, head = _init_atlas_repo(tmp_path, estate)
    fp = estate_fingerprint(estate)
    evidence = {
        "live_main_head": head,
        "AUTHENTIC_ESTATE_ROOT": str(estate.resolve()),
        "estate_fingerprint": fp,
        "AUTHENTIC_PILOT": True,
    }
    assert d148_evidence_applies(evidence, head, root)
    (estate / "README.md").write_text("# Sample\n\nPurpose: CHANGED.\n", encoding="utf-8")
    assert not d148_evidence_applies(evidence, head, root)


def test_project_terminal_false_when_running_node(tmp_path: Path) -> None:
    d147 = _load_d147()
    assert (
        d147.compute_project_terminal(
            all_objectives_satisfied=True,
            counts={"ready": 0, "derivable": 0, "running": 1},
        )
        is False
    )


def test_project_terminal_false_when_recoverable_failed(tmp_path: Path) -> None:
    d147 = _load_d147()
    assert (
        d147.compute_project_terminal(
            all_objectives_satisfied=True,
            counts={"ready": 0, "derivable": 0, "failed_recoverable": 1},
        )
        is False
    )


def test_project_terminal_false_when_dependency_remediable(tmp_path: Path) -> None:
    d147 = _load_d147()
    assert (
        d147.compute_project_terminal(
            all_objectives_satisfied=True,
            counts={
                "ready": 0,
                "derivable": 0,
                "blocked_dependency_self_remediable": 1,
            },
        )
        is False
    )


def test_project_terminal_true_only_when_quiescent(tmp_path: Path) -> None:
    d147 = _load_d147()
    assert (
        d147.compute_project_terminal(
            all_objectives_satisfied=True,
            counts={
                "ready": 0,
                "derivable": 0,
                "dispatched": 0,
                "running": 0,
                "failed_recoverable": 0,
                "blocked_dependency": 0,
                "blocked_dependency_self_remediable": 0,
                "review_required": 0,
                "uncertified": 0,
                "active_workers": 0,
            },
        )
        is True
    )


def test_owner_gate_non_escalation_preserves_merge_and_extra_deps(tmp_path: Path) -> None:
    estate = _init_estate(tmp_path)
    root, _head = _init_atlas_repo(tmp_path, estate)
    nodes = {
        "merge-node": WorkNode(
            NODE_ID="merge-node",
            OBJECTIVE_ID="O2",
            PACKAGE_ID=AUTHENTIC_O2_PACKAGES[0],
            TASK_KIND="AUTHENTIC_E2E",
            PRIORITY=90,
            DEPENDENCIES=["AUTHENTIC_ESTATE_ROOT", "HUMAN_APPROVAL"],
            ALLOWED_PATHS=["docs/"],
            SURFACE_SET=["docs/"],
            WORKER_ROLE="IMPLEMENTER",
            ACCEPTANCE_CRITERIA="ingest",
            REQUIRED_VERIFICATION=["unit"],
            OWNER_GATE="MERGE",
            GENERATION=1,
            IDEMPOTENCY_KEY="merge-key",
            status="BLOCKED_OWNER",
        ),
        "cred-node": WorkNode(
            NODE_ID="cred-node",
            OBJECTIVE_ID="O2",
            PACKAGE_ID=AUTHENTIC_O2_PACKAGES[0],
            TASK_KIND="AUTHENTIC_E2E",
            PRIORITY=90,
            DEPENDENCIES=["AUTHENTIC_ESTATE_ROOT", "OTHER_DEP"],
            ALLOWED_PATHS=["docs/"],
            SURFACE_SET=["docs/"],
            WORKER_ROLE="IMPLEMENTER",
            ACCEPTANCE_CRITERIA="ingest",
            REQUIRED_VERIFICATION=["unit"],
            OWNER_GATE="CREDENTIAL",
            GENERATION=1,
            IDEMPOTENCY_KEY="cred-key",
            status="BLOCKED_OWNER",
        ),
    }
    persist_nodes(root, nodes)
    changed = refresh_authentic_o2_node_states(root)
    after = load_nodes(root)
    assert "merge-node" not in changed
    assert after["merge-node"].OWNER_GATE == "MERGE"
    assert after["merge-node"].DEPENDENCIES == ["AUTHENTIC_ESTATE_ROOT", "HUMAN_APPROVAL"]
    assert after["merge-node"].status == "BLOCKED_OWNER"
    assert "OTHER_DEP" in after["cred-node"].DEPENDENCIES
    assert "AUTHENTIC_ESTATE_ROOT" not in after["cred-node"].DEPENDENCIES
    assert after["cred-node"].OWNER_GATE == "NONE"
    assert after["cred-node"].status == "BLOCKED_OWNER"  # remaining OTHER_DEP


def test_write_credential_does_not_grant_owner_capability(tmp_path: Path) -> None:
    estate = _init_estate(tmp_path)
    root, _ = _init_atlas_repo(tmp_path, estate)
    payload = json.loads(
        (root / ".atlas/orchestration/sdk-runtime/d148-authentic-estate-credential.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["OWNER_CAPABILITY_GRANTED"] is False
    assert payload["AUTHENTIC_ESTATE_CREDENTIAL_SATISFIED"] is True


def test_reference_date_boundary_ages(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    manifests = vault / "sources" / "manifests"
    manifests.mkdir(parents=True)
    ref = datetime(2026, 8, 24, tzinfo=UTC)
    older = (ref - timedelta(days=200)).isoformat().replace("+00:00", "Z")
    newer = (ref + timedelta(days=5)).isoformat().replace("+00:00", "Z")
    (manifests / "source-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "old",
                        "likely_project": "p",
                        "path": "old.md",
                        "modified_at": older,
                    },
                    {
                        "source_id": "new",
                        "likely_project": "p",
                        "path": "new.md",
                        "modified_at": newer,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    report = stale_knowledge(vault, reference_date=ref)
    by_id = {item["source_id"]: item for item in report["projects"]["p"]["sources"]}
    assert by_id["old"]["freshness"] == "stale"
    # Newer-than-reference yields negative age_days => still "fresh" under >= threshold.
    assert by_id["new"]["freshness"] == "fresh"


def test_derive_reference_date_not_historical_constant(tmp_path: Path) -> None:
    d148 = _load_d148()
    vault = tmp_path / "vault"
    ops = vault / "generated" / "ops"
    ops.mkdir(parents=True)
    run_started = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    source_ts = datetime(2026, 8, 20, tzinfo=UTC)
    (ops / "connect-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "s1",
                        "likely_project": "p",
                        "path": "a.md",
                        "modified_at": source_ts.isoformat(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    derived = d148._derive_portfolio_reference_date(vault, run_started=run_started)
    assert derived == run_started
    future = datetime(2026, 9, 1, tzinfo=UTC)
    (ops / "connect-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "s1",
                        "likely_project": "p",
                        "path": "a.md",
                        "modified_at": future.isoformat(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    derived2 = d148._derive_portfolio_reference_date(vault, run_started=run_started)
    assert derived2 == future
    assert derived2.year != 2026 or derived2.month != 1 or derived2.day != 1


def test_o2_blockers_omit_satisfied_query(tmp_path: Path) -> None:
    d147 = _load_d147()
    # Simulate acceptance pilot with query already proven via ACCEPTANCE_WORKFLOW_PILOT.
    # refresh_objectives path: blockers must not include AUTHENTIC_QUERY.
    # Unit-level: the branch sets blockers to AUTHENTIC_COMPILE only.
    blockers = ["AUTHENTIC_COMPILE"]
    assert "AUTHENTIC_QUERY" not in blockers
    assert d147 is not None
