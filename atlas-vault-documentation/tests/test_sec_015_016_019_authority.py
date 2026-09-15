"""CODEX-SEC-015 / SEC-016 / SEC-019 control-plane authority regressions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from agent_control import authority, bootstrap, preflight, readiness, receipt_gate, session, skill_loader

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "atlas_agent.py"
ISSUER_KEY = "test-authority-issuer-key-32chars-min!!"


def _skill() -> object:
    return skill_loader.load(ROOT / "skills" / "atlas-governed-work")


def _write_registry(path: Path, *, skill_version: str, skill_sha256: str, status: str = "passed") -> None:
    path.write_text(
        "schema_version: 1\n"
        "adapters:\n"
        "  generic-cli-v1:\n"
        f"    skill_version: {skill_version}\n"
        f"    skill_sha256: {skill_sha256}\n"
        f"    rehearsal_status: {status}\n"
        "    revoked: false\n",
        encoding="utf-8",
    )


def _project(tmp_path: Path, *, registry: Path | None) -> tuple[Path, Path]:
    project = tmp_path / "project"
    vault = tmp_path / "vault"
    (project / ".atlas").mkdir(parents=True)
    (vault / ".atlas").mkdir(parents=True)
    (vault / ".atlas" / "vault.json").write_text(
        json.dumps({"vault_id": "atlas-main", "vault_uuid": "fixture-uuid"}),
        encoding="utf-8",
    )
    readiness_line = f"  readiness_registry: {registry}\n" if registry is not None else ""
    (project / ".atlas" / "project.yaml").write_text(
        "schema_version: 1\n"
        "project:\n"
        "  id: authority-fixture\n"
        "  name: Authority Fixture\n"
        "documentation:\n"
        "  skill_id: atlas-governed-work\n"
        "  strict: true\n"
        f"{readiness_line}"
        "vault:\n"
        "  required_vault_id: atlas-main\n",
        encoding="utf-8",
    )
    return project, vault


def test_sec015_missing_readiness_configuration_denies(tmp_path: Path) -> None:
    project, vault = _project(tmp_path, registry=None)
    report = readiness.check(None, "generic-cli-v1", "1.0.0", "a" * 64)
    assert report["authorized"] is False
    assert report["status"] == "not-configured"
    with pytest.raises(ValueError, match="readiness registry is not configured"):
        preflight.run(
            project_root=project,
            vault_root=vault,
            agent_type="generic",
            agent_value="agent-a",
            skill_root=ROOT / "skills" / "atlas-governed-work",
        )


def test_sec015_missing_registry_file_denies(tmp_path: Path) -> None:
    missing = tmp_path / "missing-readiness.yaml"
    project, vault = _project(tmp_path, registry=missing)
    with pytest.raises(ValueError, match="readiness registry is missing"):
        preflight.run(
            project_root=project,
            vault_root=vault,
            agent_type="generic",
            agent_value="agent-a",
            skill_root=ROOT / "skills" / "atlas-governed-work",
        )


def test_sec016_receipt_is_evidence_not_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill = _skill()
    monkeypatch.setenv("ATLAS_MDA_COMMAND", str(ROOT / "tests" / "fixtures" / "bin" / "mda"))
    registry = tmp_path / "readiness.yaml"
    _write_registry(registry, skill_version=skill.version, skill_sha256=skill.sha256)
    project, vault = _project(tmp_path, registry=registry)
    state, _ = bootstrap.start(
        project_root=project,
        vault_root=vault,
        agent_type="generic",
        agent_value="agent-receipt",
        task_id="AS-SKILL-001",
        skill_root=ROOT / "skills" / "atlas-governed-work",
    )
    sid = str(state["session"]["session_id"])
    from agent_control import event_client, skill_ack, capability

    skill_ack.acknowledge(vault, sid, skill.skill_id, skill.version, skill.sha256)
    capability.check(vault, sid)
    for event_type in ("session-start", "validation", "completion"):
        event_client.document(vault_root=vault, session_id=sid, event_type=event_type, summary=event_type)
    final = session.load(vault, sid)
    receipt = receipt_gate.issue(vault, final)
    assert receipt["is_authority"] is False
    assert receipt["receipt_is_authority"] is False
    assert receipt["authority_role"] == "evidence-only"

    receipt_path = vault / ".atlas" / "receipts" / f"{receipt['receipt_id']}.json"
    # Promote without an independent grant must fail (receipt alone is not authority).
    env = dict(os.environ)
    env.pop(authority.ISSUER_ENV, None)
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "promote-readiness",
            "--registry",
            str(registry),
            "--adapter-id",
            "generic-cli-v1",
            "--rehearsal-id",
            str(receipt["rehearsal"]["rehearsal_id"]),
            "--receipt",
            str(receipt_path),
            "--skill-id",
            skill.skill_id,
            "--skill-version",
            skill.version,
            "--skill-sha256",
            skill.sha256,
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "authority-grant" in (result.stderr + result.stdout).lower() or "required" in (result.stderr + result.stdout).lower()


def test_sec019_cli_cannot_self_approve_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill = _skill()
    monkeypatch.setenv("ATLAS_MDA_COMMAND", str(ROOT / "tests" / "fixtures" / "bin" / "mda"))
    registry = tmp_path / "readiness.yaml"
    _write_registry(registry, skill_version=skill.version, skill_sha256=skill.sha256, status="pending")
    project, vault = _project(tmp_path, registry=registry)
    # Bootstrap still denied while pending — use a temporary passed registry for session evidence.
    passed = tmp_path / "passed.yaml"
    _write_registry(passed, skill_version=skill.version, skill_sha256=skill.sha256, status="passed")
    (project / ".atlas" / "project.yaml").write_text(
        (project / ".atlas" / "project.yaml").read_text(encoding="utf-8").replace(str(registry), str(passed)),
        encoding="utf-8",
    )
    state, _ = bootstrap.start(
        project_root=project,
        vault_root=vault,
        agent_type="generic",
        agent_value="self-agent",
        task_id="AS-SKILL-001",
        skill_root=ROOT / "skills" / "atlas-governed-work",
    )
    sid = str(state["session"]["session_id"])
    from agent_control import event_client, skill_ack, capability

    skill_ack.acknowledge(vault, sid, skill.skill_id, skill.version, skill.sha256)
    capability.check(vault, sid)
    for event_type in ("session-start", "validation", "completion"):
        event_client.document(vault_root=vault, session_id=sid, event_type=event_type, summary=event_type)
    final = session.load(vault, sid)
    receipt = receipt_gate.issue(vault, final)
    receipt_path = vault / ".atlas" / "receipts" / f"{receipt['receipt_id']}.json"
    store = tmp_path / "authority"
    monkeypatch.setenv(authority.ISSUER_ENV, ISSUER_KEY)
    agent_id = str(final["agent"]["agent_id"])

    # Self-issued grant (issuer == requester) must be rejected at GRANT time.
    with pytest.raises(ValueError, match="issuer must not equal requester"):
        authority.issue_grant(
            store=store,
            purpose=authority.PURPOSE_PROMOTE_READINESS,
            adapter_id="generic-cli-v1",
            skill_id=skill.skill_id,
            skill_version=skill.version,
            skill_sha256=skill.sha256,
            issuer_id=agent_id,
            requester_id=agent_id,
            evidence_receipt_id=receipt["receipt_id"],
        )

    # Independent grant succeeds; promotion uses GRANT not receipt hash theater.
    grant = authority.issue_grant(
        store=store,
        purpose=authority.PURPOSE_PROMOTE_READINESS,
        adapter_id="generic-cli-v1",
        skill_id=skill.skill_id,
        skill_version=skill.version,
        skill_sha256=skill.sha256,
        issuer_id="human-operator-issuer",
        requester_id=agent_id,
        evidence_receipt_id=receipt["receipt_id"],
    )
    grant_path = store / "grants" / f"{grant['grant_id']}.json"

    # Tampered attacker-controlled JSON with recomputed sha256 of itself still fails MAC.
    forged = dict(grant)
    forged["issuer_id"] = agent_id
    forged_path = tmp_path / "forged-grant.json"
    forged_path.write_text(json.dumps(forged, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity check failed"):
        authority.verify_grant(
            forged_path,
            purpose=authority.PURPOSE_PROMOTE_READINESS,
            adapter_id="generic-cli-v1",
            skill_id=skill.skill_id,
            skill_version=skill.version,
            skill_sha256=skill.sha256,
            requester_id=agent_id,
            evidence_receipt_id=receipt["receipt_id"],
            store=store,
        )

    env = dict(os.environ, **{authority.ISSUER_ENV: ISSUER_KEY})
    promoted = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "promote-readiness",
            "--registry",
            str(registry),
            "--adapter-id",
            "generic-cli-v1",
            "--rehearsal-id",
            str(receipt["rehearsal"]["rehearsal_id"]),
            "--receipt",
            str(receipt_path),
            "--authority-grant",
            str(grant_path),
            "--authority-store",
            str(store),
            "--skill-id",
            skill.skill_id,
            "--skill-version",
            skill.version,
            "--skill-sha256",
            skill.sha256,
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert promoted.returncode == 0, promoted.stderr
    payload = json.loads(promoted.stdout)
    assert payload["result"] == "promoted"
    assert payload["authority_grant_id"] == grant["grant_id"]
    data = yaml.safe_load(registry.read_text(encoding="utf-8"))
    assert data["adapters"]["generic-cli-v1"]["rehearsal_status"] == "passed"
    assert data["adapters"]["generic-cli-v1"]["rehearsal"]["authority_grant_id"] == grant["grant_id"]

    # Revocation blocks reuse.
    authority.revoke_grant(store=store, grant_id=str(grant["grant_id"]))
    with pytest.raises(ValueError, match="revoked"):
        authority.verify_grant(
            grant_path,
            purpose=authority.PURPOSE_PROMOTE_READINESS,
            adapter_id="generic-cli-v1",
            skill_id=skill.skill_id,
            skill_version=skill.version,
            skill_sha256=skill.sha256,
            requester_id=agent_id,
            evidence_receipt_id=receipt["receipt_id"],
            store=store,
        )


def test_sec016_hash_of_attacker_json_is_not_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Security theater: hashing attacker-controlled JSON must not authorize promote."""
    skill = _skill()
    monkeypatch.setenv(authority.ISSUER_ENV, ISSUER_KEY)
    store = tmp_path / "authority"
    attacker = {
        "schema_version": 1,
        "grant_type": "atlas-authority-grant",
        "grant_id": "AAG-attacker",
        "purpose": authority.PURPOSE_PROMOTE_READINESS,
        "subject": {
            "adapter_id": "generic-cli-v1",
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
            "skill_sha256": skill.sha256,
        },
        "issuer_id": "attacker",
        "requester_id": "victim",
        "evidence_receipt_id": None,
        "revoked": False,
        "authority_role": "grant",
        "receipt_is_authority": False,
    }
    # Attacker "protects" payload by hashing their own bytes — not an issuer MAC.
    attacker["mac"] = hashlib.sha256(json.dumps(attacker, sort_keys=True).encode()).hexdigest()
    path = tmp_path / "attacker-grant.json"
    path.write_text(json.dumps(attacker, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity check failed"):
        authority.verify_grant(
            path,
            purpose=authority.PURPOSE_PROMOTE_READINESS,
            adapter_id="generic-cli-v1",
            skill_id=skill.skill_id,
            skill_version=skill.version,
            skill_sha256=skill.sha256,
            requester_id="victim",
            store=store,
        )
