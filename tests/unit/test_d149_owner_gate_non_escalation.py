"""D-149 — authentic estate must not grant owner authority."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.autonomy.authentic_estate import (
    AUTHENTIC_ESTATE_DEPENDENCY,
    AuthenticO2PreflightError,
    apply_authentic_estate_mutations,
    estate_fingerprint,
    estate_prerequisite_consumable,
    load_estate_credential,
    refresh_authentic_o2_node_states,
    run_estate_preflight,
    validate_authentic_o2_pre_mutation,
    write_estate_credential,
)
from project_atlas.orchestration.autonomy.exact_main_closure import (
    ClosureIntegrity,
    git_object_pin,
)
from project_atlas.orchestration.sdk.mission_reconciler import (
    WorkNode,
    load_nodes,
    persist_nodes,
)


def _init_git(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)
    return path


def _write_marker(estate: Path, *, project_id: str = "sample") -> None:
    (estate / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: "
        f"{project_id}\n  name: Sample\nproject_uuid: "
        "00000000-0000-4000-8000-000000000001\n",
        encoding="utf-8",
    )


def _valid_estate(tmp_path: Path, *, name: str = "estate", project_id: str = "sample") -> Path:
    estate = _init_git(tmp_path / name)
    _write_marker(estate, project_id=project_id)
    subprocess.run(["git", "add", "-A"], cwd=estate, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "marker"], cwd=estate, check=True, capture_output=True)
    return estate


def _atlas_repo(tmp_path: Path) -> Path:
    return _init_git(tmp_path / "atlas")


def _o2_node(
    *,
    node_id: str,
    package: str = "AS-CODER-ALPHA-AUTHENTIC-INGEST-001",
    owner_gate: str = "CREDENTIAL",
    dependencies: list[str] | None = None,
    status: str = "BLOCKED_OWNER",
) -> WorkNode:
    return WorkNode(
        NODE_ID=node_id,
        OBJECTIVE_ID="O2",
        PACKAGE_ID=package,
        TASK_KIND="IMPLEMENTATION",
        PRIORITY=90,
        DEPENDENCIES=list(
            dependencies if dependencies is not None else [AUTHENTIC_ESTATE_DEPENDENCY]
        ),
        ALLOWED_PATHS=["src/project_atlas/"],
        SURFACE_SET=["src/project_atlas/"],
        WORKER_ROLE="IMPLEMENTER",
        ACCEPTANCE_CRITERIA="d149",
        REQUIRED_VERIFICATION=["unit"],
        OWNER_GATE=owner_gate,  # type: ignore[arg-type]
        GENERATION=1,
        IDEMPOTENCY_KEY=node_id,
        status=status,  # type: ignore[arg-type]
        fingerprint=node_id,
    )


def _bind_estate(monkeypatch: pytest.MonkeyPatch, estate: Path) -> None:
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(estate))


def _failing_integrity(repo: Path) -> ClosureIntegrity:
    live = git_object_pin(repo, "HEAD")
    return ClosureIntegrity(
        live_main_head=live.head,
        live_main_tree=live.tree,
        certification_target_head=live.head,
        certification_target_tree=live.tree,
        certification_target_is_ancestor_of_live_main=True,
        live_head_tree_coherent=True,
        cert_target_head_tree_coherent=True,
        operational_pins_match_cert_target=False,
        live_matches_integrated_main=True,
    )


def test_helper_rejects_protected_owner_gates() -> None:
    deps = [AUTHENTIC_ESTATE_DEPENDENCY]
    assert estate_prerequisite_consumable(owner_gate="CREDENTIAL", dependencies=deps)
    for gate in ("MERGE", "SECURITY", "HUMAN", "OWNER", "RELEASE", "GOVERNOR", "SIGNOFF"):
        assert not estate_prerequisite_consumable(owner_gate=gate, dependencies=deps)


def test_credential_plus_estate_root_becomes_runnable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    changed = refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["n1"]
    assert changed == ["n1"]
    assert node.status == "READY"
    assert node.OWNER_GATE == "NONE"
    assert node.DEPENDENCIES == []


@pytest.mark.parametrize("gate", ["MERGE", "SECURITY"])
def test_protected_gate_not_rewritten_to_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1", owner_gate=gate)})
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["n1"]
    assert gate == node.OWNER_GATE
    assert node.status == "BLOCKED_OWNER"
    assert AUTHENTIC_ESTATE_DEPENDENCY in node.DEPENDENCIES


def test_adversarial_merge_gate_cannot_become_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Primary D-149 adversarial case: estate availability must not clear MERGE."""
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"merge": _o2_node(node_id="merge", owner_gate="MERGE")})
    _bind_estate(monkeypatch, estate)
    written = write_estate_credential(repo, estate, run_estate_preflight(estate))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["OWNER_CAPABILITY_GRANTED"] is False
    refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["merge"]
    assert node.OWNER_GATE == "MERGE"
    assert node.status != "READY"


def test_other_credential_remains_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(
        repo,
        {"n1": _o2_node(node_id="n1", dependencies=["OTHER_OWNER_CREDENTIAL"])},
    )
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["n1"]
    assert node.OWNER_GATE == "CREDENTIAL"
    assert node.status == "BLOCKED_OWNER"
    assert node.DEPENDENCIES == ["OTHER_OWNER_CREDENTIAL"]


def test_consumes_estate_dependency_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(
        repo,
        {
            "n1": _o2_node(
                node_id="n1",
                dependencies=[AUTHENTIC_ESTATE_DEPENDENCY, "AS-CODER-ALPHA-AUTHENTIC-INGEST-001"],
            )
        },
    )
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["n1"]
    assert node.DEPENDENCIES == ["AS-CODER-ALPHA-AUTHENTIC-INGEST-001"]
    assert node.status == "BLOCKED_OWNER"
    assert node.OWNER_GATE == "NONE"


def test_invalid_estate_does_not_widen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing-estate"
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    monkeypatch.setenv("AUTHENTIC_ESTATE_ROOT", str(missing))
    assert refresh_authentic_o2_node_states(repo) == []
    node = load_nodes(repo)["n1"]
    assert node.OWNER_GATE == "CREDENTIAL"
    assert node.status == "BLOCKED_OWNER"


def test_missing_project_marker_does_not_widen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _init_git(tmp_path / "estate")
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    assert not run_estate_preflight(estate).preflight_pass
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    assert load_estate_credential(repo)["OWNER_CAPABILITY_GRANTED"] is False
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_malformed_marker_does_not_widen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _init_git(tmp_path / "estate")
    (estate / ".atlas-project.yaml").write_text("not: valid: yaml: [[", encoding="utf-8")
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    assert not run_estate_preflight(estate).preflight_pass
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_stale_estate_credential_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    cred_path = (
        repo / ".atlas" / "orchestration" / "sdk-runtime" / "d148-authentic-estate-credential.json"
    )
    payload = json.loads(cred_path.read_text(encoding="utf-8"))
    payload["estate_fingerprint"] = "0" * 64
    cred_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_stale_main_binding_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    cred_path = (
        repo / ".atlas" / "orchestration" / "sdk-runtime" / "d148-authentic-estate-credential.json"
    )
    payload = json.loads(cred_path.read_text(encoding="utf-8"))
    payload["live_main_head"] = "a" * 40
    cred_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].status == "BLOCKED_OWNER"


def test_closure_integrity_failure_does_not_mutate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    integrity = _failing_integrity(repo)
    with pytest.raises(AuthenticO2PreflightError, match="closure integrity"):
        validate_authentic_o2_pre_mutation(repo, estate, integrity=integrity)
    cred = (
        repo / ".atlas" / "orchestration" / "sdk-runtime" / "d148-authentic-estate-credential.json"
    )
    assert not cred.is_file()
    assert refresh_authentic_o2_node_states(repo, integrity=integrity) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_exception_after_preflight_restores_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1", owner_gate="MERGE")})
    _bind_estate(monkeypatch, estate)
    preflight = run_estate_preflight(estate)

    def _boom(*_args: Any, **_kwargs: Any) -> list[str]:
        raise RuntimeError("post-preflight failure")

    monkeypatch.setattr(
        "project_atlas.orchestration.autonomy.authentic_estate.refresh_authentic_o2_node_states",
        _boom,
    )
    with pytest.raises(RuntimeError, match="post-preflight"):
        apply_authentic_estate_mutations(repo, estate, preflight)
    cred = (
        repo / ".atlas" / "orchestration" / "sdk-runtime" / "d148-authentic-estate-credential.json"
    )
    assert not cred.is_file()
    assert load_nodes(repo)["n1"].OWNER_GATE == "MERGE"


def test_repeated_reconciliation_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    first = refresh_authentic_o2_node_states(repo)
    second = refresh_authentic_o2_node_states(repo)
    third = refresh_authentic_o2_node_states(repo)
    assert first == ["n1"]
    assert second == []
    assert third == []
    node = load_nodes(repo)["n1"]
    assert node.status == "READY"
    assert node.OWNER_GATE == "NONE"


def test_existing_ready_node_remains_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(
        repo,
        {
            "ready": _o2_node(
                node_id="ready",
                owner_gate="NONE",
                dependencies=[],
                status="READY",
            )
        },
    )
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    assert refresh_authentic_o2_node_states(repo) == []
    node = load_nodes(repo)["ready"]
    assert node.status == "READY"
    assert node.OWNER_GATE == "NONE"
    assert node.DEPENDENCIES == []


def test_cross_project_credential_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate_a = _valid_estate(tmp_path, name="estate-a", project_id="alpha")
    estate_b = _valid_estate(tmp_path, name="estate-b", project_id="beta")
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    write_estate_credential(repo, estate_a, run_estate_preflight(estate_a))
    _bind_estate(monkeypatch, estate_b)
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_demo_fixture_cannot_masquerade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _init_git(tmp_path / "tests" / "fixtures" / "harbor-api")
    _write_marker(fixture, project_id="harbor-api")
    repo = _atlas_repo(tmp_path)
    persist_nodes(repo, {"n1": _o2_node(node_id="n1")})
    _bind_estate(monkeypatch, fixture)
    preflight = run_estate_preflight(fixture)
    assert not preflight.preflight_pass
    write_estate_credential(repo, fixture, preflight)
    assert load_estate_credential(repo)["OWNER_CAPABILITY_GRANTED"] is False
    assert load_estate_credential(repo)["AUTHENTIC_ESTATE_ROOT_AVAILABLE"] is False
    assert refresh_authentic_o2_node_states(repo) == []
    assert load_nodes(repo)["n1"].OWNER_GATE == "CREDENTIAL"


def test_write_estate_credential_never_grants_owner_capability(
    tmp_path: Path,
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    payload = json.loads(
        write_estate_credential(repo, estate, run_estate_preflight(estate)).read_text(
            encoding="utf-8"
        )
    )
    assert payload["OWNER_CAPABILITY_GRANTED"] is False
    assert payload["AUTHENTIC_ESTATE_ROOT_AVAILABLE"] is True
    assert payload["estate_does_not_grant_owner_authority"] is True
    assert payload["estate_fingerprint"] == estate_fingerprint(estate)


def test_d148_preflight_regression_still_passes(tmp_path: Path) -> None:
    estate = _valid_estate(tmp_path)
    preflight = run_estate_preflight(estate)
    assert preflight.preflight_pass
    assert preflight.project_id == "sample"


def test_stale_certification_does_not_advance_compile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estate = _valid_estate(tmp_path)
    repo = _atlas_repo(tmp_path)
    persist_nodes(
        repo,
        {
            "compile": _o2_node(
                node_id="compile",
                package="AS-CODER-ALPHA-AUTHENTIC-COMPILE-001",
            )
        },
    )
    cert_dir = repo / ".atlas" / "orchestration" / "sdk-runtime"
    cert_dir.mkdir(parents=True, exist_ok=True)
    (cert_dir / "d148-o2-certification.json").write_text(
        json.dumps(
            {
                "AUTHENTIC_INGEST_SATISFIED": True,
                "live_main_head": "b" * 40,
                "AUTHENTIC_ESTATE_ROOT": str(estate.resolve()),
                "estate_fingerprint": estate_fingerprint(estate),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _bind_estate(monkeypatch, estate)
    write_estate_credential(repo, estate, run_estate_preflight(estate))
    refresh_authentic_o2_node_states(repo)
    node = load_nodes(repo)["compile"]
    assert node.status == "BLOCKED_OWNER"
    assert node.DEPENDENCIES == []
    assert node.OWNER_GATE == "NONE"


def test_env_restored_after_module_use() -> None:
    """Guard against leaking AUTHENTIC_ESTATE_ROOT into later tests."""
    assert os.environ.get("AUTHENTIC_ESTATE_ROOT") in {None, ""}
